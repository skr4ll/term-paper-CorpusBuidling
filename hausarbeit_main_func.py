def create_corpus_file(transcripts, metadata, output_folder):
    negator_words = ["pas", "plus", "guère", "point", "jamais", "rien", "aucun"]
    for i, (transcript, meta) in enumerate(zip(transcripts, metadata)):
        cleaned_trans = remove_brackets(transcript)
        output_file = os.path.join(output_folder, f"{meta['video_id']}.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(
                f'<doc region="north" title="{meta["video_title"]}" date="{meta["published_date"]}" channel="{meta["channel_name"]}" source="https://www.youtube.com/watch?v={meta["video_id"]}">\n')
            f.write("<s>\n")  # Start of <s> tag
            doc = nlp(cleaned_trans)
            index = 0
            while index < len(doc):
                next_token = doc[index + 1] if index + 1 < len(doc) else None
                second_next_token = doc[index + 2] if index + 2 < len(doc) else None
                third_next_token = doc[index + 3] if index + 3 < len(doc) else None
                if doc[index].text in ["ne", "n'"]:
                    if next_token and second_next_token and (
                           next_token.pos_ == "PRON" and second_next_token.pos_ == "VERB"):
                        f.write(f'<negation full="true">{doc[index].text} {next_token.text} {second_next_token.text}</negation>')
                    elif next_token and (next_token.pos_ == "VERB"):
                        f.write(f'<negation full="true">{doc[index].text} {next_token.text} {doc[index + 2].text}</negation>')
