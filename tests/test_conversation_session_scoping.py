import sys
import os
import pytest
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.response_engine.engine import ResponseEngine
from src.response_engine.models import EngineInput
from src.services.database import init_db, SessionLocal, ChatHistory, save_chat_message

def test_returning_user_fresh_chat_time_gap():
    """Test 1: Returning user with old history (> 10m gap) starts fresh chat.
    Turn 1 must return pattern_name = none."""
    init_db()
    db = SessionLocal()
    user_id = "test_user_scoping_gap"
    try:
        db.query(ChatHistory).filter(ChatHistory.user_id == user_id).delete()
        db.commit()
    finally:
        db.close()

    # Create old chat history from 1 hour ago
    old_time = datetime.now(timezone.utc) - timedelta(minutes=60)
    
    # Save old messages to DB manually with old timestamp
    db = SessionLocal()
    try:
        msg1 = ChatHistory(user_id=user_id, role="user", content="Bugün çok mutsuzum.", timestamp=old_time)
        msg2 = ChatHistory(user_id=user_id, role="user", content="Hiçbir şeyden keyif alamıyorum.", timestamp=old_time)
        db.add(msg1)
        db.add(msg2)
        db.commit()
    finally:
        db.close()

    engine = ResponseEngine()
    
    # Now send the first message of a new session (Turn 1).
    # Since the last message in DB is from 60 minutes ago, the gap > 10 min, 
    # so the old messages must be discarded for pattern detection.
    engine_input = EngineInput(
        text="Bugün kendimi çok mutsuz hissediyorum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr"
    )
    output = engine.generate_response(engine_input)
    assert "conversation_pattern" in output.metadata
    pat = output.metadata["conversation_pattern"]
    assert pat["pattern_name"] == "none"


def test_three_related_turns_same_session_with_id():
    """Test 2: Same current session has 3 related user turns.
    Turn 3 returns withdrawal_pattern."""
    init_db()
    engine = ResponseEngine()
    user_id = "test_user_scoping_session_id"
    session_id = "session_abc_123"

    # Turn 1
    inp1 = EngineInput(
        text="Bugün çok mutsuzum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr",
        session_id=session_id
    )
    res1 = engine.generate_response(inp1)
    assert res1.metadata["conversation_pattern"]["pattern_name"] == "none"

    # Turn 2
    inp2 = EngineInput(
        text="Hiçbir şeyden keyif alamıyorum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr",
        session_id=session_id
    )
    res2 = engine.generate_response(inp2)
    assert res2.metadata["conversation_pattern"]["pattern_name"] == "none"

    # Turn 3
    inp3 = EngineInput(
        text="Kimseyle konuşmak istemiyorum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr",
        session_id=session_id
    )
    res3 = engine.generate_response(inp3)
    assert res3.metadata["conversation_pattern"]["pattern_name"] == "withdrawal_pattern"
    assert res3.metadata["conversation_pattern"]["confidence"] >= 0.70


def test_old_session_does_not_affect_new_session():
    """Test 3: Old session messages must not affect new session pattern detection."""
    init_db()
    engine = ResponseEngine()
    user_id = "test_user_scoping_two_sessions"
    
    # Session 1: sends 2 withdrawal-related messages
    inp1 = EngineInput(
        text="Bugün çok mutsuzum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr",
        session_id="session_1"
    )
    engine.generate_response(inp1)
    
    inp2 = EngineInput(
        text="Hiçbir şeyden keyif alamıyorum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr",
        session_id="session_1"
    )
    engine.generate_response(inp2)

    # Session 2 starts fresh. Turn 1 should not trigger withdrawal even though
    # session_1 has withdrawal-related messages.
    inp3 = EngineInput(
        text="Kimseyle konuşmak istemiyorum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr",
        session_id="session_2"
    )
    res3 = engine.generate_response(inp3)
    assert res3.metadata["conversation_pattern"]["pattern_name"] == "none"


def test_crisis_input_bypasses_pattern():
    """Test 4: Crisis input still bypasses all pattern detection."""
    init_db()
    engine = ResponseEngine()
    user_id = "test_user_scoping_crisis"
    session_id = "session_crisis_999"

    # Turn 1
    inp1 = EngineInput(
        text="Bugün çok mutsuzum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr",
        session_id=session_id
    )
    engine.generate_response(inp1)

    # Turn 2
    inp2 = EngineInput(
        text="Hiçbir şeyden keyif alamıyorum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr",
        session_id=session_id
    )
    engine.generate_response(inp2)

    # Turn 3: Crisis risk label should immediately bypass pattern detection
    inp3 = EngineInput(
        text="Artık yaşamak istemiyorum.",
        emotion="sadness",
        risk="crisis",
        user_id=user_id,
        language="tr",
        session_id=session_id
    )
    res3 = engine.generate_response(inp3)
    assert res3.metadata.get("is_crisis") is True
    
    # Check that either pattern is none or absent
    pat = res3.metadata.get("conversation_pattern")
    if pat:
        assert pat["pattern_name"] == "none"
