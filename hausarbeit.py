import spacy
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import re

# Laden des französischen Language Models
nlp = spacy.load("fr_core_news_sm")


# Authentifizierungsfunktion an der YouTube Data API V3
def auth_process():
    credentials = None
    # token.pickle speichert die Credentials von vorherigen erfolgreichen Logins
    if os.path.exists('token.pickle'):
        print('Loading Credentials From File...')
        with open('token.pickle', 'rb') as token:
            credentials = pickle.load(token)

    # Existieren keine gültigen Credentials werden sie refreshed oder ein erneuter Login getriggert
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print('Refreshing Access Token...')
            credentials.refresh(Request())
        else:
            print('Fetching New Tokens...')
            flow = InstalledAppFlow.from_client_secrets_file(
                'NEWclient_secret.json',
                scopes=[
                    'https://www.googleapis.com/auth/youtube.readonly'
                ]
            )

            flow.run_local_server(port=8080, prompt='consent',
                                  authorization_prompt_message='')
            credentials = flow.credentials

            # Credentials für nächsten Durchlauf speichern
            with open('token.pickle', 'wb') as f:
                print('Saving Credentials for Future Use...')
                pickle.dump(credentials, f)

    return credentials


credentials = auth_process()

#  Anfrage über contentDetails der  Playlist
youtube = build('youtube', 'v3', credentials=credentials)

request = youtube.playlistItems().list(
    part="contentDetails",
    playlistId="ID",
    maxResults='1000',
    prettyPrint="true"
)
response = request.execute()

video_ids = []

for item in response['items']:
    video_id = item['contentDetails']['videoId']
    video_ids.append(video_id)

video_metadata = {}

# Iteration über jede video_id in der Playlist um auf die Metadaten zuzugreifen
for video_id in video_ids:
    video_response = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()

    # Die video_details werden extrahiert
    video_details = video_response['items'][0]['snippet']

    # Metadaten des jeweiligen Videos werden dem Dictionary hinzugefügt
    video_metadata[video_id] = {
        "video_id": video_id,
        "video_title": video_details['title'],
        "channel_name": video_details['channelTitle'],
        "published_date": video_details['publishedAt']
    }


# Download des YouTube Transkript anhand der video_id
def download_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['fr'])
        return ' '.join([line['text'] for line in transcript])
    except Exception as e:
        print(f"Error downloading transcript for video ID {video_id}: {e}")
        return None


# Hilfsfunktion zur Bereinigung des Transkripts
def remove_brackets(text):
    return re.sub(r'\[.*?\]', '', text)


# Kernfunktion zur Verarbeitung der Transkripte
def create_corpus_file(transcripts, metadata, output_folder):
    negator_words = ["pas", "plus", "guère", "point", "jamais", "rien", "aucun"]
    for i, (transcript, meta) in enumerate(zip(transcripts, metadata)):
        # Entfernen aller Angaben in eckigen Klammern aus dem Transkript
        cleaned_trans = remove_brackets(transcript)
        output_file = os.path.join(output_folder, f"{meta['video_id']}.txt")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(
                f'<doc region="west" title="{meta["video_title"]}" date="{meta["published_date"]}" '
                f'channel="{meta["channel_name"]}" source="https://www.youtube.com/watch?v={meta["video_id"]}">\n')
            f.write("<s>\n")  # Start of <s> tag
            # Das Transkript muss von "SPACE" tokens bereinigt werden, da diese problematisch bei der Verarbeitung sind
            unclean_doc = nlp(cleaned_trans)
            cleaned_doc = [token.text for token in unclean_doc if token.pos_ != "SPACE"]
            cleaned_text = " ".join(cleaned_doc)
            doc = nlp(cleaned_text)
            index = 0
            while index < len(doc):
                curr_token = doc[index] if index < len(doc) else None
                next_token = doc[index + 1] if index + 1 < len(doc) else None
                second_next_token = doc[index + 2] if index + 2 < len(doc) else None
                third_next_token = doc[index + 3] if index + 3 < len(doc) else None
                fourth_next_token = doc[index + 4] if index + 4 < len(doc) else None

                # if curr_token.text == "vote" and next_token.text == "pas":
                #     print(f'"{doc[index -1].text}___ {doc[index-1].pos_} {curr_token.text}___{curr_token.pos_} {next_token.text}___{next_token.pos_}"')
                print(f'"Currently processing video with ID: {meta["video_id"]} '
                      f'and token: {curr_token.text}___{curr_token.pos_} at index: {index}"')

                # Da SpaCy n' als 2 Tokens betrachtet muss dieser Fall behandelt werden
                if curr_token.text == "ne" or (curr_token.text == "n" and next_token.text == "'"):
                    # Wegen der getrennten Tokenisierung von n und ', muss leider so vorgegangen werden.
                    # Die Token n und ' werden gemerged und die anderen Token, sowie der Index um 1 erhöht
                    if curr_token.text == "n":
                        negator_token = curr_token.text + next_token.text
                        next_token = doc[index + 2] if index + 2 < len(doc) else None
                        second_next_token = doc[index + 3] if index + 3 < len(doc) else None
                        third_next_token = doc[index + 4] if index + 4 < len(doc) else None
                        fourth_next_token = doc[index + 5] if index + 5 < len(doc) else None
                        index += 1
                    else:
                        negator_token = curr_token.text

                    # Die Fälle in denen eine vollständige Negation vorliegt
                    # (ne/n' + PRON + VERB + NEG-ADV oder ne/n' + VERB + NEG-ADV)
                    # NOUN wird inkludiert um Taggingfehlern zuvorzukommen (siehe paper).

                    # Negation mit Pronomen:
                    # Wird auch mit "DET" getaggt je nach Satz
                    if next_token and second_next_token and (
                            (next_token.pos_ in ["PRON", "PUNCT", "DET"]
                             and second_next_token.pos_ in ["VERB", "AUX", "NOUN"])):
                        f.write(
                            f'<negation full="true" negationParticle="{negator_token}">{negator_token} {next_token.text} {second_next_token.text} '
                            f'{third_next_token.text}</negation>')
                        index += 4

                    # Mit ne/n' + PRON + PRON +VERB
                    elif next_token and third_next_token and (next_token.pos_ in ["PRON", "PUNCT", "DET"]
                                                              and second_next_token.pos_ in ["PRON", "PUNCT", "DET"]
                                                              and third_next_token in ["VERB", "AUX", "NOUN"]):
                        f.write(
                            f'<negation full="true" negationParticle="{negator_token}">{negator_token} {next_token.text} {second_next_token.text} '
                            f'{third_next_token.text} {fourth_next_token.text}</negation>')
                        index += 5

                    # Negation ohne Pronomen:
                    elif next_token and (next_token.pos_ in ["VERB", "AUX", "NOUN", "PUNCT"]):
                        f.write(
                            f'<negation full="true" negationParticle="{negator_token}">{negator_token} {next_token.text} '
                            f'{second_next_token.text}</negation>')
                        index += 3

                    # Das "ne" erscheint direkt gefolgt von negator_word. Wird als full-negation betrachtet
                    elif next_token and (next_token.lemma_ in negator_words):
                        f.write(
                            f'<negation full="true" negationParticle="{negator_token}">{negator_token} {next_token.text} '
                            f'{second_next_token.text}</negation>')
                        index += 3
                    # Zweig um mögliche Fehlausführung des Skripts durch
                    # nicht abgefangene Fälle zu verhindern (mindert die Datenqualität)
                    else:
                        f.write(f'{curr_token.text} ')
                        index += 1

                # Die Fälle in denen keine "volle" Negation vorliegt. Es gibt kein vorangestelltes "ne" bzw. "n'".
                # Ob es ein next_token gibt muss geprüft werden.
                # Zur Sicherheit wird auch auf NOUN geprüft (mögliche Taggingfehler)
                elif curr_token.pos_ in ["VERB", "NOUN"] and (next_token and next_token.lemma_ in negator_words):
                    f.write(
                        f'<negation full="false" negationParticle="none">{curr_token.text} {next_token.text}</negation>')
                    index += 2
                elif curr_token:
                    f.write(f'{curr_token.text} ')
                    index += 1
                else:
                    f.write(f'{curr_token.text} ')
                    index += 1

            f.write("</s>\n")
            f.write("</doc>")


# Aufruf zum Download der Transkripte
transcripts = []
for video_id in video_ids:
    print("getting video with id: " + video_id)
    transcript = download_transcript(video_id)
    if transcript:
        transcripts.append(transcript)
output_folder = "FOLDER"
# Aufruf der Kernfunktion, zur Verarbeitung (tagging, markup und schreiben in eine Textdatei)
create_corpus_file(transcripts, video_metadata.values(), output_folder)
