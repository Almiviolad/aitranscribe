from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from pytubefix import YouTube
from pytubefix.cli import on_progress
from django.conf import settings
import os
import assemblyai as aai
import openai
from .models import Transcript


# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

# get youtube title
def yt_title(link):
    yt = YouTube(link)
    return yt.title

# get the youtube audio
def get_yt_audio(link):
    yt = YouTube(link,on_progress_callback = on_progress)
    video = yt.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

# turn auido to text using asseblyai
def get_transcription(link):
    audio_file = get_yt_audio(link)
    aai.settings.api_key = '9bf5632ddbd64c27929565304283f89a'

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    print(transcript.text)

    return transcript.text

# coming aack to this 
def generate_transcript(transcript_text):
    import requests
    API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
    headers = {}  # No Authorization header needed

    prompt = (
        "Turn the following transcript into a clear, professional tutorial. "
        "Avoid casual YouTube-style writing. Make it look like a real blog post or guide.\n\n"
        f"Transcript:\n{transcript_text}\n\nTutorial:"
    )

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 700, "temperature": 0.7}
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    result = response.json()

    # Sometimes the response structure can vary
    if isinstance(result, list):
        return result[0]['generated_text']
    elif 'generated_text' in result:
        return result['generated_text']
    else:
        return str(result)


@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return  JsonResponse({'Error': 'Invalid data sent'}, status=400)
        
        # get title
        title = yt_title(yt_link)

        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'Error': 'Failed to get transcript'}, status=500)
        
        # use openai to genertae transcript
        content = transcription
        if not content:
            return JsonResponse({'Error': 'Failed to get transcript tutorial'}, status=500)
        
        # save tarsncript to db
        new_transcript = Transcript.objects.create(
            user = request.user,
            youtube_title = title,
            youtube_link = yt_link,
            generated_content = content,
        )
        new_transcript.save()
        # return transdcript as response
        return JsonResponse({'content': content})

    else:
        return JsonResponse({'Error': 'Invalid request method'}, status=405)


def transcripts(request):
    all_transcripts = Transcript.objects.filter(user=request.user)
    return render(request, 'all_transcripts.html', {'transcripts': all_transcripts})

def transcript_details(request, pk):
    transcript_details = Transcript.objects.get(id=pk)
    if request.user == transcript_details.user:
        return render(request, 'transcript_detail.html', {'transcript_details': transcript_details})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, login.html, {'error_message': error_message})
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeat_password = request.POST['repeat_password']

        if password == repeat_password:
            try:
                user = User.objects.create_user(username, email=email, password=password)
                user.save()
                login(request, user)
                return redirect('/')
            except Exception as e:
                error_message = f"Error creating user: ({e})"
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message': error_message})
    return render(request, 'signup.html')

def user_logout(request):
     logout(request)
     return redirect('/')