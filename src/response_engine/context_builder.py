"""
context_builder.py — Context-Aware Conversation Memory Manager
Faz 5 Prompt 4

Strategy (priority order):
    1. Most recent user messages (always included)
    2. Crisis-flagged history (always preserved)
    3. Emotion-continuous messages (same/related emotion chain)
    4. Recent topic continuity (recent assistant turns)
    5. Older low-relevance history (trimmed first)

Limits (configurable via ContextConfig):
    max_history_messages  = 12   (raw DB fetch ceiling)
    max_context_chars     = 4000 (total char budget for history)
    max_single_msg_chars  = 800  (single message truncation limit)
"""

import logging
import unicodedata
from typing import List, Dict, Any, Optional, Tuple

from src.services.database import get_chat_history

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & Config
# ---------------------------------------------------------------------------

MAX_HISTORY_MESSAGES: int = 12       # ceiling for DB fetch
MAX_CONTEXT_CHARS: int = 4_000       # total char budget for all history
MAX_SINGLE_MSG_CHARS: int = 800      # hard cap per individual message
CRISIS_RISK_LABELS = {"1", "crisis", "kriz"}
EMOTION_GROUPS = {
    "sad":     {"sadness", "sad", "depressed", "grief"},
    "anxious": {"anxiety", "fear", "worried", "anxious", "panic"},
    "angry":   {"anger", "angry", "frustrated", "rage"},
    "happy":   {"happiness", "happy", "joy", "excited"},
    "neutral": {"neutral", "calm"},
}


def _normalize(text: str) -> str:
    """NFC-normalize and strip — preserves UTF-8 safety."""
    return unicodedata.normalize("NFC", text).strip()


def _truncate(text: str, max_chars: int) -> str:
    """Hard-truncate to max_chars, appending ellipsis if cut."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1] + "…"


def _emotion_group(emotion: str) -> Optional[str]:
    """Return canonical emotion group key, or None if unknown."""
    lower = emotion.lower()
    for group, labels in EMOTION_GROUPS.items():
        if lower in labels:
            return group
    return None


def _is_crisis(risk: str) -> bool:
    return risk.strip().lower() in CRISIS_RISK_LABELS


def _deduplicate(messages: List[Dict]) -> List[Dict]:
    """
    Remove strictly consecutive duplicate messages.
    Only drops a message if the immediately preceding message has the same
    (role, normalized_content) — non-consecutive repeats are preserved.

    Example:
        [A, A, B, A]  →  [A, B, A]   (first A-A collapsed, trailing A kept)
        [A, B, A]     →  [A, B, A]   (not consecutive — all kept)
    """
    deduped: List[Dict] = []
    for msg in messages:
        key = (msg.get("role", ""), _normalize(msg.get("content", "")))
        if deduped:
            prev_key = (deduped[-1].get("role", ""), _normalize(deduped[-1].get("content", "")))
            if key == prev_key:
                continue  # exact consecutive duplicate — skip
        deduped.append(msg)
    return deduped


def _score_message(
    msg: Dict,
    index: int,
    total: int,
    current_emotion_group: Optional[str],
    is_crisis_session: bool,
) -> float:
    """
    Assign a relevance score to a history message.
    Higher score = higher priority for inclusion.

    Scoring factors:
        - Recency          (newest = 1.0, oldest = 0.0, linear)
        - Crisis content   (+0.5 bonus — always preserved)
        - Emotion match    (+0.25 bonus — continuity)
        - Role             (user messages slightly preferred)
    """
    # Recency: linear decay (index 0 = oldest)
    recency = index / max(total - 1, 1)         # 0.0 → 1.0

    # Crisis bonus
    content_lower = msg.get("content", "").lower()
    crisis_keywords = (
        "kriz", "intihar", "zarar", "öldür", "yardım", "112",
        "crisis", "suicide", "harm", "emergency"
    )
    crisis_bonus = 0.5 if any(kw in content_lower for kw in crisis_keywords) else 0.0

    # Emotion continuity bonus
    emotion_bonus = 0.0
    if current_emotion_group:
        emotion_keywords = EMOTION_GROUPS.get(current_emotion_group, set())
        if any(kw in content_lower for kw in emotion_keywords):
            emotion_bonus = 0.25

    # Role bonus (user messages carry more semantic payload)
    role_bonus = 0.05 if msg.get("role") == "user" else 0.0

    return recency + crisis_bonus + emotion_bonus + role_bonus


def _select_context(
    history: List[Dict],
    current_emotion: str,
    current_risk: str,
    max_history: int = MAX_HISTORY_MESSAGES,
    max_chars: int = MAX_CONTEXT_CHARS,
    max_single: int = MAX_SINGLE_MSG_CHARS,
) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Core context selection algorithm.

    Returns:
        (selected_messages, context_metadata)

    Algorithm:
        1. Fetch up to max_history raw messages
        2. Deduplicate consecutive identical messages
        3. Truncate individual messages to max_single_msg_chars
        4. Score each message by relevance
        5. Always lock in the last 2 user+assistant pairs (recency anchor)
        6. Fill remaining char budget by descending score
        7. Restore chronological order for GPT
    """
    if not history:
        return [], {
            "history_message_count": 0,
            "selected_context_count": 0,
            "context_trimmed": False,
            "estimated_context_chars": 0,
        }

    emotion_group = _emotion_group(current_emotion)
    is_crisis_session = _is_crisis(current_risk)

    # Step 1: Deduplicate
    history = _deduplicate(history)

    # Step 2: Per-message truncation (safe UTF-8 via _normalize)
    for msg in history:
        msg["content"] = _truncate(_normalize(msg.get("content", "")), max_single)

    total = len(history)

    # Step 3: Score each message
    scored = [
        (i, _score_message(history[i], i, total, emotion_group, is_crisis_session), history[i])
        for i in range(total)
    ]

    # Step 4: Lock in recency anchor — last 4 messages (2 user+assistant pairs)
    # These are ALWAYS included regardless of score.
    anchor_count = min(4, total)
    anchor_indices = set(range(total - anchor_count, total))
    anchor_messages = [history[i] for i in sorted(anchor_indices)]
    anchor_chars = sum(len(m["content"]) for m in anchor_messages)

    # Remaining budget after anchors
    remaining_budget = max_chars - anchor_chars

    # Step 5: Fill from remaining non-anchor messages by descending score
    non_anchor = [(i, score, msg) for (i, score, msg) in scored if i not in anchor_indices]
    non_anchor.sort(key=lambda x: x[1], reverse=True)

    selected_indices = set(anchor_indices)
    used_chars = anchor_chars

    for idx, score, msg in non_anchor:
        msg_chars = len(msg["content"])
        # Crisis sessions: be extra conservative with budget
        budget_check = remaining_budget if not is_crisis_session else remaining_budget * 0.8
        if used_chars + msg_chars <= used_chars + budget_check and msg_chars <= remaining_budget:
            if used_chars + msg_chars <= max_chars:
                selected_indices.add(idx)
                used_chars += msg_chars

    # Step 6: Rebuild in chronological order
    selected = [history[i] for i in sorted(selected_indices)]

    context_trimmed = (len(selected) < total)

    meta: Dict[str, Any] = {
        "history_message_count": total,
        "selected_context_count": len(selected),
        "context_trimmed": context_trimmed,
        "estimated_context_chars": used_chars,
        "emotion_group": emotion_group,
        "is_crisis_session": is_crisis_session,
    }

    return selected, meta


def build_messages(
    user_id: str,
    system_prompt: str,
    user_prompt: str,
    limit: int = MAX_HISTORY_MESSAGES,
    emotion: str = "neutral",
    risk: str = "Normal",
) -> List[Dict[str, str]]:
    """
    Builds the complete GPT message list.

    Pipeline:
        [system]  ← system_prompt
        [history] ← context-selected, deduplicated, budget-aware history
        [user]    ← current user_prompt

    Args:
        user_id:       Used to fetch per-user history.
        system_prompt: Already-built system prompt from prompts.py.
        user_prompt:   Current turn user message.
        limit:         Max raw history messages to fetch from DB.
        emotion:       Current detected emotion (for context scoring).
        risk:          Current detected risk level (for crisis context handling).

    Returns:
        List of {"role": ..., "content": ...} dicts ready for OpenAI API.
    """
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    raw_history: List[Dict] = []
    try:
        raw_history = get_chat_history(user_id, limit=limit)
    except Exception as e:
        logger.error(f"Context | Failed to fetch history for user {user_id}: {e}")
        # Graceful degradation: continue without history

    # Run context selection
    selected, meta = _select_context(
        history=raw_history,
        current_emotion=emotion,
        current_risk=risk,
        max_history=limit,
        max_chars=MAX_CONTEXT_CHARS,
        max_single=MAX_SINGLE_MSG_CHARS,
    )

    # Structured context log — only role/metadata, no user content
    logger.info(
        "CONTEXT_LOG | UserID: %s | Emotion: %s | Risk: %s | "
        "history_message_count: %d | selected_context_count: %d | "
        "context_trimmed: %s | estimated_context_chars: %d",
        user_id,
        emotion,
        risk,
        meta["history_message_count"],
        meta["selected_context_count"],
        meta["context_trimmed"],
        meta["estimated_context_chars"],
    )

    # Append selected history (only role + content, strip DB metadata)
    for entry in selected:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Append current turn
    messages.append({"role": "user", "content": user_prompt})

    return messages
