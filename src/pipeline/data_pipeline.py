import pandas as pd
import os

def create_datasets(input_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    # Read data
    print("Reading dataset...")
    df = pd.read_csv(input_path)
    
    # Emotion dataset
    # We will use 'text' and the integer 'label' from cleaned_emotions
    emotion_df = df[['text', 'label']].copy()
    
    emotion_out = os.path.join(output_dir, 'emotion_dataset.csv')
    emotion_df.to_csv(emotion_out, index=False)
    print(f"[{len(emotion_df)} rows] Saved emotion dataset to {emotion_out}")
    
    # Crisis dataset
    # Rule based: 1 if emotion is sadness/fear and has crisis keywords
    print("Generating crisis labels...")
    crisis_keywords = ['suicide', 'kill', 'die', 'dead', 'hopeless', 'pain', 'end it', 'give up', 'cutting', 'self harm', 'hurt myself', 'worthless', 'depressed', 'nobody cares', 'hate my life']
    
    def is_crisis(row):
        text = str(row['text']).lower()
        # label 1 is üzgün (sadness), 2 is kaygılı (fear)
        if row['label'] in [1, 2]:
            if any(keyword in text for keyword in crisis_keywords):
                return 1
        return 0

    df['crisis_label'] = df.apply(is_crisis, axis=1)
    crisis_df = df[['text', 'crisis_label']].rename(columns={'crisis_label': 'label'})
    
    crisis_out = os.path.join(output_dir, 'crisis_dataset.csv')
    crisis_df.to_csv(crisis_out, index=False)
    print(f"[{len(crisis_df)} rows] Saved crisis dataset to {crisis_out}")
    print(f"Found {crisis_df['label'].sum()} total crisis examples.")

if __name__ == "__main__":
    create_datasets("data/cleaned_emotions.csv", "data/processed")
