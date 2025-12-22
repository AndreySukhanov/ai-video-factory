"""
Merge 3 episode videos into one final video
"""
import os
import json
import urllib.request

# Video URLs from the test
VIDEOS = [
    {
        "episode": 1,
        "url": "https://replicate.delivery/xezq/5FlTPlJjfBz5Hypp2V3ar0HlsEBcpPKlbUettfAicocrKamrA/tmpdyra4cuz.mp4"
    },
    {
        "episode": 2,
        "url": "https://replicate.delivery/xezq/3aTz2xc3SOJJPNezDkApbE2EfSeuIar3ba1n87WmRFFkMamrA/tmpnocxzuoq.mp4"
    },
    {
        "episode": 3,
        "url": "https://replicate.delivery/xezq/87XsDI2X3eXpLSkVKFv76xveIdqErMMLE1Qwb7Vd9K5KHNzVA/tmpuv4l5x2t.mp4"
    }
]

OUTPUT_DIR = "output"
FINAL_VIDEO = "sofia_miniseries_full.mp4"

def download_videos():
    """Download all episode videos"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    files = []
    for video in VIDEOS:
        filename = f"{OUTPUT_DIR}/episode_{video['episode']}.mp4"
        print(f"Downloading Episode {video['episode']}...")
        urllib.request.urlretrieve(video['url'], filename)
        files.append(filename)
        print(f"  Saved: {filename}")
    
    return files

def create_concat_file(files):
    """Create FFmpeg concat file"""
    concat_file = f"{OUTPUT_DIR}/concat_list.txt"
    with open(concat_file, "w") as f:
        for file in files:
            # Use relative path for FFmpeg
            f.write(f"file '{os.path.basename(file)}'\n")
    return concat_file

def merge_videos():
    """Merge videos using FFmpeg"""
    print("\nMerging videos with FFmpeg...")
    
    output_path = f"{OUTPUT_DIR}/{FINAL_VIDEO}"
    
    # FFmpeg concat command
    cmd = f'ffmpeg -y -f concat -safe 0 -i "{OUTPUT_DIR}/concat_list.txt" -c copy "{output_path}"'
    
    print(f"Running: {cmd}")
    result = os.system(cmd)
    
    if result == 0:
        print(f"\nSUCCESS! Final video: {output_path}")
        return output_path
    else:
        print(f"\nERROR: FFmpeg failed with code {result}")
        return None

def main():
    print("="*60)
    print("MERGING 3 EPISODES INTO ONE VIDEO")
    print("="*60)
    
    # Download videos
    print("\n1. Downloading episode videos...")
    files = download_videos()
    
    # Create concat file
    print("\n2. Creating concat list...")
    create_concat_file(files)
    
    # Merge
    print("\n3. Merging videos...")
    result = merge_videos()
    
    if result:
        print("\n" + "="*60)
        print("DONE!")
        print(f"Final video: {os.path.abspath(result)}")
        print("="*60)

if __name__ == "__main__":
    main()
