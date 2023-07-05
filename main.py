import hashlib
import json
import openai
import os
import requests
import sys
import traceback
import uuid

# Create the output directory if it doesn't exist
output_directory = "./output"
os.makedirs(output_directory, exist_ok=True)

openai.api_key = os.getenv("OPENAI_API_KEY")
chat_completion_model = "gpt-3.5-turbo"

download_api_url = "https://co.wuk.sh/api/json"
download_api_request_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def makeAudioFile(video_url):
    mp3_download_response = requests.post(
            download_api_url,
            headers=download_api_request_headers,
            json={
                "url": video_url,
                "isAudioOnly": "true"
            }
    )
    mp3_download_response.raise_for_status()
    mp3_download_data = mp3_download_response.json()
    mp3_download_url = mp3_download_data['url']
    
    mp3_audio_response = requests.get(mp3_download_url)
    mp3_audio_response.raise_for_status()
    mp3_audio_data = mp3_audio_response.content

    with open(mp3_file_path, "wb") as file:
        file.write(mp3_audio_data)
    
    print("Audio file created successfully!")

def makeTranscriptFile(mp3_file_path):
    with open(mp3_file_path, "rb") as mp3_file:
        transcript_response = openai.Audio.transcribe("whisper-1", mp3_file)
    transcript_string = transcript_response.text

    with open(transcript_file_path, "w", encoding="utf-8") as transcript_file:
        transcript_file.write(transcript_string)

    print("Audio transcribed succesfully!")

def makeSummaryJsonFile(transcript_file_path):
    with open(transcript_file_path, "r", encoding="utf-8") as transcript_file:
        transcript = transcript_file.read()

        chat_completion = openai.ChatCompletion.create(
            model=chat_completion_model,
            messages=[
                {
                    "role": "system", "content": '''
                        You are a helpful video summarization assistant.
                        
                        You will receive a video transcript from the user.
                        Please do your best to understand the transcript
                        and return the following JSON object:
                        {
                            "title": "A descriptive 3 to 5 word title (alphanumeric)",
                            "points": ["An array of the points covered in the video"],
                            "summary": "A concise summary of the video",
                            "logline": "A single-sentence summary of the video",
                            "comments": "Your comments and observations about the video",
                            "tags": ["An array of tags categorizing the video"],
                        }

                        REMEMBER: The title may not be more than 5 words or use any symbols!
                    '''
                },
                { "role": "user", "content": f'Here is the transcript: """{transcript}"""' }
            ]
        )
     
        chat_completion_content = json.loads(chat_completion['choices'][0]['message']['content'])
        chat_completion_content["transcript"] = transcript
     
        with open(json_summary_file_path, "w", encoding="utf-8") as json_summary_file:
            json.dump(chat_completion_content, json_summary_file, indent=2)

        print("Transcript summarized to JSON successfully!")

def makeMarkdownSummaryFile(json_summary_data, markdown_summary_file_path):
    with open(markdown_summary_file_path, "w", encoding="utf-8") as markdown_summary_file:
        markdown_contents = (
            f'***{json_summary_data["logline"]}***\n\n'
            '## Summary\n' + json_summary_data['summary'] + '\n\n'
            '## Points\n' + '\n'.join(['- ' + point for point in json_summary_data['points']]) + '\n\n'
            '## Comments\n' + json_summary_data['comments'] + '\n\n'
            '## Tags\n' + '\n'.join(['- ' + tag for tag in json_summary_data['tags']]) + '\n\n'
            '## Transcript\n' + json_summary_data['transcript']
        )
        
        markdown_summary_file.write(markdown_contents)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Please provide the URL as an argument.")
        sys.exit(1)

    video_url = sys.argv[1]
    file_uuid = uuid.uuid5(uuid.NAMESPACE_URL, hashlib.md5(video_url.encode('utf-8')).hexdigest())

    mp3_file_name = f"{file_uuid}.mp3"
    mp3_file_path = os.path.join(output_directory, mp3_file_name)
    if os.path.exists(mp3_file_path):
        print("Using cached audio file...")
    else:
        print("Using audio download API...")
        try:
            makeAudioFile(video_url)
        except requests.exceptions.HTTPError as e:
            print("Audio file download call failed with error:", str(e))
        except:
            print("An unexpected error occured:")
            traceback.print_exc()

    transcript_file_name = f"{file_uuid}_transcript.txt"
    transcript_file_path = os.path.join(output_directory, transcript_file_name)
    if os.path.exists(transcript_file_path):
        print("Using cached transcript file...")
    else:
        print("Using transcription API...")
        try:
            makeTranscriptFile(mp3_file_path)
        except:
            print("An unexpected error occured:")
            traceback.print_exc()

    json_summary_file_name = f"{file_uuid}_summary.json"
    json_summary_file_path = os.path.join(output_directory, json_summary_file_name)
    if os.path.exists(json_summary_file_path):
        print("Using cached JSON summary file...")
    else:
        print("Using JSON summary API...")
        try:
            makeSummaryJsonFile(transcript_file_path)
        except requests.exceptions.HTTPError as e:
            print("Audio file download call failed with error:", str(e))
        except:
            print("An unexpected error occured:")
            traceback.print_exc()

    with open(json_summary_file_path) as json_summary_file:
        json_summary_data = json.load(json_summary_file)

        markdown_summary_file_name = f"{file_uuid}_{json_summary_data['title']}.md"
        markdown_summary_file_path = os.path.join(output_directory, markdown_summary_file_name)

        if os.path.exists(markdown_summary_file_path):
            print(f"Summary alreaady exists! {markdown_summary_file_path}")
        else:
            print("Making markdown summary file!")
            makeMarkdownSummaryFile(json_summary_data, markdown_summary_file_path)
