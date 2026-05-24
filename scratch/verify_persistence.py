import sys
import os
import shutil
import time

# Ensure we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.database import (
    init_db,
    SessionLocal,
    UserMemory,
    create_memory,
    get_memories_for_user,
    cleanup_old_memories,
    clear_user_memories_db
)
from src.response_engine.memory_manager import (
    process_memory,
    clear_user_memory,
    get_user_memory_summary
)

def run_tests():
    print("==================================================")
    print("STARTING PERSISTENT MEMORY SYSTEM (PHASE 7) TESTS")
    print("==================================================")
    
    # 1. Initialize Database
    print("\n[TEST 1/6] Database Initialization...")
    init_db()
    print("SUCCESS: Database initialized successfully.")

    # Let's use a unique test user
    user_id = "test_user_phase7"
    
    # Clean any old test records first
    clear_user_memories_db(user_id)

    # 2. Duplicate Memory Protection & Confidence Boosting
    print("\n[TEST 2/6] Duplicate Memory Protection...")
    # Trigger 1: create memory
    m_key = "user_preferences"
    m_val = "Kullanıcı Türkçe konuşulmasını tercih ediyor."
    
    success1 = create_memory(
        user_id=user_id,
        memory_key=m_key,
        memory_value=m_val,
        emotion="normal",
        source_message="Türkçe konuşalım lütfen.",
        confidence=0.7
    )
    
    # Fetch and check
    mems_after_1 = get_memories_for_user(user_id)
    assert len(mems_after_1) == 1, f"Expected 1 memory, got {len(mems_after_1)}"
    orig_conf = mems_after_1[0]["confidence"]
    orig_updated = mems_after_1[0]["updated_at"]
    print(f"  - First insertion success. Confidence: {orig_conf}")
    
    # Wait briefly to ensure timestamp difference if updated
    time.sleep(0.5)

    # Trigger 2: identical memory (simulate duplicate observation)
    success2 = create_memory(
        user_id=user_id,
        memory_key=m_key,
        memory_value=m_val,
        emotion="normal",
        source_message="Tekrar ediyorum, Türkçe.",
        confidence=0.7
    )
    
    mems_after_2 = get_memories_for_user(user_id)
    assert len(mems_after_2) == 1, f"Expected duplicate protection to keep size 1, got {len(mems_after_2)}"
    new_conf = mems_after_2[0]["confidence"]
    new_updated = mems_after_2[0]["updated_at"]
    
    print(f"  - Duplicate check completed.")
    print(f"  - Boosted Confidence: {new_conf} (Original: {orig_conf})")
    print(f"  - Updated Timestamp: {new_updated} (Original: {orig_updated})")
    assert new_conf > orig_conf, "Confidence should have boosted!"
    print("SUCCESS: Duplicate protection and confidence boosting verified.")

    # 3. Limit & Rolling Cleanup Strategy
    print("\n[TEST 3/6] Limit & Cleanup Strategy...")
    # Clear test user memories
    clear_user_memories_db(user_id)
    
    # Insert 55 memories
    for i in range(1, 56):
        create_memory(
            user_id=user_id,
            memory_key="coping_strategies",
            memory_value=f"Stres yönetimi yöntemi #{i}",
            emotion="stresli",
            confidence=0.5 + (i * 0.005) # varying confidence
        )
    
    # Run cleanup
    cleanup_old_memories(user_id, max_limit=50)
    
    mems_trimmed = get_memories_for_user(user_id)
    print(f"  - Inserted 55 memories, ran cleanup.")
    print(f"  - Total count after cleanup: {len(mems_trimmed)}")
    assert len(mems_trimmed) == 50, f"Expected exactly 50 memories, got {len(mems_trimmed)}"
    print("SUCCESS: Limits and rolling cleanup strategy verified.")

    # 4. Restart Persistence Simulation
    print("\n[TEST 4/6] Restart Persistence Simulation...")
    # Clear memories
    clear_user_memories_db(user_id)
    
    # Extract new memory via memory_manager process_memory
    text_input = "meditasyon bana iyi geliyor."
    meta = process_memory(
        user_id=user_id,
        text=text_input,
        emotion="normal",
        risk="0",
        privacy_mode=False
    )
    
    print(f"  - Process memory run. Memory Count: {meta['memory_count']}")
    
    # Fetch from SQLite to confirm persistence
    rows_db = get_memories_for_user(user_id)
    assert len(rows_db) > 0, "No memories recorded in DB!"
    extracted_val = rows_db[0]["memory_value"]
    print(f"  - Extracted memory in DB: '{extracted_val}'")
    
    # Simulate restart by instantiating process_memory pipeline again
    # We will call it with a prompt that triggers a lookup keyword match
    lookup_input = "meditasyon yapacağım."
    meta_lookup = process_memory(
        user_id=user_id,
        text=lookup_input,
        emotion="stresli",
        risk="0",
        privacy_mode=False
    )
    
    print(f"  - After simulated restart, look up memory context:")
    print(f"  - Context Injected: {meta_lookup['memory_injected']}")
    print(f"  - Context Text:\n{meta_lookup['injection_text']}")
    
    assert meta_lookup['memory_injected'] is True, "Memory should have been injected!"
    assert "meditasyon" in meta_lookup['injection_text'].lower(), "Injected text should mention 'meditasyon'!"
    print("SUCCESS: Persistence and lookup verified across simulated restarts.")

    # 5. Privacy Mode Complete Suppression
    print("\n[TEST 5/6] Privacy Mode Enforcement...")
    # Clean user memories
    clear_user_memories_db(user_id)
    
    # Send a request with privacy_mode=True
    meta_privacy = process_memory(
        user_id=user_id,
        text="Köpek beslemek beni çok mutlu ediyor.",
        emotion="normal",
        risk="0",
        privacy_mode=True
    )
    
    rows_privacy = get_memories_for_user(user_id)
    print(f"  - Processed message with privacy_mode=True.")
    print(f"  - DB Memories Count: {len(rows_privacy)}")
    print(f"  - Memory Injected Status: {meta_privacy['memory_injected']}")
    assert len(rows_privacy) == 0, "Privacy mode failed! Memories were written to DB."
    assert meta_privacy['memory_injected'] is False, "Privacy mode failed! Memory lookup occurred."
    print("SUCCESS: Privacy mode completely blocks all extraction and injection.")

    # 6. Crisis Override Safeguards
    print("\n[TEST 6/6] Crisis Safety Safeguards...")
    # Clean user memories
    clear_user_memories_db(user_id)
    
    # Send a request containing crisis risk/sentiment
    meta_crisis = process_memory(
        user_id=user_id,
        text="Artık dayanamıyorum, kendime zarar vermek istiyorum.",
        emotion="korku",
        risk="crisis",
        privacy_mode=False
    )
    
    rows_crisis = get_memories_for_user(user_id)
    print(f"  - Processed message with risk='crisis'.")
    print(f"  - DB Memories Count: {len(rows_crisis)}")
    print(f"  - Memory Injected Status: {meta_crisis['memory_injected']}")
    assert len(rows_crisis) == 0, "Crisis safety failed! Crisis thoughts recorded to DB."
    assert meta_crisis['memory_injected'] is False, "Crisis safety failed! Lookups allowed during crisis turn."
    print("SUCCESS: Crisis context completely suppressed memory extraction and injection.")

    print("\n==================================================")
    print("ALL PERSISTENT MEMORY TESTS PASSED SUCCESSFULY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
