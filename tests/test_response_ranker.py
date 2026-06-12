import sys
sys.path.insert(0, ".")

from src.response_engine.response_ranker import (
    score_response, check_empty, check_too_short, check_repetitive,
    check_generic, check_context_mismatch, check_crisis_unsafe,
    NORMAL_THRESHOLD, CRISIS_THRESHOLD, RankResult
)

errors = []

def assert_eq(label, got, expected):
    if got != expected:
        errors.append(f"FAIL [{label}]: got {got!r}, expected {expected!r}")
    else:
        print(f"  OK  [{label}]")

def assert_true(label, cond):
    if not cond:
        errors.append(f"FAIL [{label}]: condition was False")
    else:
        print(f"  OK  [{label}]")

print("=== check_empty ===")
assert_eq("empty string",  check_empty(""),      ("empty_response", 1.0))
assert_eq("whitespace",    check_empty("   "),   ("empty_response", 1.0))
assert_eq("valid text",    check_empty("Merhaba bu bir test mesajıdır."), None)

print("\n=== check_too_short ===")
assert_eq("too short normal",  check_too_short("Anlıyorum.", False), ("too_short", 0.5))
long_enough = "Bu bir test mesajı olup yeterince uzundur ne düşünüyorsunuz acaba bakıyorum"
assert_eq("long enough normal", check_too_short(long_enough, False), None)
crisis_short = "Güvende ol lütfen yardım al"
assert_eq("too short crisis",  check_too_short(crisis_short, True), ("too_short", 0.5))

print("\n=== check_repetitive ===")
repetitive = "tamam tamam tamam tamam tamam tamam tamam tamam tamam tamam"
assert_eq("repetitive",    check_repetitive(repetitive),  ("repetitive", 0.3))
normal_text = "Seni duyabiliyorum ve bu süreçte yanındayım her zaman."
assert_eq("non-repetitive", check_repetitive(normal_text), None)

print("\n=== check_generic ===")
assert_eq("generic opener short", check_generic("anlıyorum"),  ("generic_response", 0.1))
assert_eq("generic but long",     check_generic("anlıyorum bu durumun seni çok zorladığını ve seninle bu süreci paylaşmak istiyorum"), None)
assert_eq("non-generic",          check_generic("Şu an çok zor bir dönemden geçiyor olabilirsin."), None)

print("\n=== check_context_mismatch ===")
mismatch = check_context_mismatch("Harika mükemmel süper wonderful!", "sadness")
assert_eq("mismatch: positive response to sadness", mismatch, ("context_mismatch", 0.3))
no_mismatch = check_context_mismatch("Seni duyabiliyorum, bu süreç zor.", "sadness")
assert_eq("no mismatch: empathetic response to sadness", no_mismatch, None)
neutral_ok = check_context_mismatch("Harika mükemmel!", "neutral")
assert_eq("neutral emotion: no mismatch", neutral_ok, None)

print("\n=== check_crisis_unsafe ===")
safe_crisis_resp = "Güvenliğiniz önemli, lütfen 112'yi arayın ve yardım alın."
assert_eq("crisis safe (has anchor)", check_crisis_unsafe(safe_crisis_resp, True), None)
unsafe_crisis = "Evet bunu anlıyorum gerçekten çok doğru bir şey."
assert_eq("crisis unsafe (no anchor)", check_crisis_unsafe(unsafe_crisis, True), ("crisis_unsafe", 1.0))
assert_eq("non-crisis: skip check",    check_crisis_unsafe(unsafe_crisis, False), None)

print("\n=== score_response: normal pass ===")
good_resp = "Seni duyabiliyorum. Böyle hissetmek gerçekten zor olabilir. Yalnız olmadığını bilmeni istiyorum, buradayım."
r = score_response(good_resp, emotion="sadness", risk="Normal")
print(f"  score={r.score:.4f} passes={r.passes} reasons={r.reasons}")
assert_true("normal good response passes", r.passes)
assert_true("score >= NORMAL_THRESHOLD", r.score >= NORMAL_THRESHOLD)

print("\n=== score_response: normal fail (too short + generic) ===")
bad_resp = "anlıyorum"
r2 = score_response(bad_resp, emotion="neutral", risk="Normal")
print(f"  score={r2.score:.4f} passes={r2.passes} reasons={r2.reasons}")
assert_true("short generic fails", not r2.passes)
assert_true("needs_retry set", r2.needs_retry)
assert_true("needs_fallback NOT set in normal", not r2.needs_fallback)

print("\n=== score_response: crisis pass ===")
crisis_resp = "Şu an güvende olmanız çok önemli. Lütfen hemen 112'yi arayın veya bir yakınınızdan destek isteyin. Yalnız değilsiniz."
r3 = score_response(crisis_resp, emotion="sadness", risk="1")
print(f"  score={r3.score:.4f} passes={r3.passes} reasons={r3.reasons}")
assert_true("crisis good response passes", r3.passes)

print("\n=== score_response: crisis fail ===")
crisis_bad = "anlıyorum"
r4 = score_response(crisis_bad, emotion="sadness", risk="kriz")
print(f"  score={r4.score:.4f} passes={r4.passes} reasons={r4.reasons}")
assert_true("crisis bad fails", not r4.passes)
assert_true("needs_fallback set in crisis", r4.needs_fallback)
assert_true("needs_retry NOT set in crisis", not r4.needs_retry)

print("\n=== RankResult.to_dict ===")
d = r4.to_dict()
assert_true("to_dict has quality_score", "quality_score" in d)
assert_true("to_dict has quality_reasons", "quality_reasons" in d)
assert_true("to_dict has needs_retry", "needs_retry" in d)
assert_true("to_dict has needs_fallback", "needs_fallback" in d)

print()
if errors:
    for e in errors:
        print(e)
    raise SystemExit(f"\n{len(errors)} assertion(s) FAILED")
else:
    print(f"All assertions PASSED ({16} checks)")
