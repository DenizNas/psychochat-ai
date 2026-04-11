import os
import csv
import shutil
import random

# Base paths
base_dir = r"c:\Users\deniz\OneDrive\Masaüstü\YAZILIM\psikochat-ai\data"
raw_dir = os.path.join(base_dir, "raw")
raw_emo = os.path.join(raw_dir, "emotion")
raw_cri = os.path.join(raw_dir, "crisis")
interim_dir = os.path.join(base_dir, "interim")
processed_dir = os.path.join(base_dir, "processed")

# Create directories
os.makedirs(raw_emo, exist_ok=True)
os.makedirs(raw_cri, exist_ok=True)
os.makedirs(interim_dir, exist_ok=True)
os.makedirs(processed_dir, exist_ok=True)

# Helper function to safely move files into raw
def move_to_raw(src_folder, dest_folder):
    if not os.path.exists(src_folder):
        return
    for item in os.listdir(src_folder):
        src_path = os.path.join(src_folder, item)
        # Skip if it's the raw folder itself or a directory
        if os.path.isdir(src_path) or src_folder == dest_folder:
            continue
        dest_path = os.path.join(dest_folder, item)
        # Only move if the source is not already in the destination
        if os.path.abspath(src_path) != os.path.abspath(dest_path):
            shutil.move(src_path, dest_path)

# Move existing files to raw
move_to_raw(os.path.join(base_dir, "emotion"), raw_emo)
move_to_raw(os.path.join(base_dir, "crisis"), raw_cri)

# If the old directories are empty, remove them
for old_d in ["emotion", "crisis"]:
    old_path = os.path.join(base_dir, old_d)
    if os.path.exists(old_path) and not os.listdir(old_path):
         os.rmdir(old_path)

def process_datasets(input_folder, output_interim, output_processed, is_crisis=False):
    all_data = []
    
    for file in os.listdir(input_folder):
        if not file.endswith('.csv'):
             continue
        file_path = os.path.join(input_folder, file)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                try:
                    headers = next(reader)
                except StopIteration:
                    continue
                
                # Normalize headers: remove BOM
                headers = [h.replace('\ufeff', '').strip().lower() for h in headers]
                
                text_idx = -1
                label_idx = -1
                aug_text_idx = -1
                
                if 'text' in headers:
                    text_idx = headers.index('text')
                
                if not is_crisis:
                    if 'label' in headers:
                        label_idx = headers.index('label')
                else:
                    if 'target' in headers:
                        label_idx = headers.index('target')
                    elif 'label' in headers:
                         label_idx = headers.index('label')
                    if 'augmented_text' in headers:
                        aug_text_idx = headers.index('augmented_text')
                
                if text_idx == -1 or label_idx == -1:
                    print(f"Skipping {file}: missing text or label/target column.")
                    continue
                
                for row in reader:
                    if len(row) <= max(text_idx, label_idx):
                        continue
                        
                    clean_text = row[text_idx].strip().replace('\n', ' ').replace('\r', '')
                    clean_label = row[label_idx].strip()
                    
                    if clean_text and clean_label:
                        all_data.append((clean_text, clean_label))
                        
                    if is_crisis and aug_text_idx != -1 and len(row) > aug_text_idx:
                        aug_text = row[aug_text_idx].strip().replace('\n', ' ').replace('\r', '')
                        if aug_text and clean_label:
                             all_data.append((aug_text, clean_label))
        except Exception as e:
            print(f"Error reading {file}: {e}")

    # Write to interim
    with open(output_interim, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['text', 'label'])
        writer.writerows(all_data)
        
    # Remove duplicates and empty rows for processed
    unique_data = list(set(all_data))
    # Optionally shuffle
    random.shuffle(unique_data)
    
    with open(output_processed, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['text', 'label'])
        writer.writerows(unique_data)
        
    print(f"Saved {len(all_data)} rows to {os.path.basename(output_interim)}")
    print(f"Saved {len(unique_data)} unique rows to {os.path.basename(output_processed)}")

# Process Emotion
process_datasets(
    raw_emo, 
    os.path.join(interim_dir, "emotion_cleaned.csv"),
    os.path.join(processed_dir, "emotion_dataset_final.csv"),
    is_crisis=False
)

# Process Crisis
process_datasets(
    raw_cri, 
    os.path.join(interim_dir, "crisis_cleaned.csv"),
    os.path.join(processed_dir, "crisis_dataset_final.csv"),
    is_crisis=True
)
