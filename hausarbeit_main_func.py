def create_corpus_file(transcripts, metadata, output_folder):
    negator_words = ["pas", "plus", "guère", "point", "jamais", "rien", "aucun"]
    for i, (transcript, meta) in enumerate(zip(transcripts, metadata)):
        # Entfernen aller Angaben in eckigen Klammern aus dem Transkript
        cleaned_trans = remove_brackets(transcript)
        output_file = os.path.join(output_folder, f"{meta['video_id']}.txt")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(
                f'<doc region="south" title="{meta["video_title"]}" date="{meta["published_date"]}" '
                f'channel="{meta["channel_name"]}" source="https://www.youtube.com/watch?v={meta["video_id"]}">\n')
            f.write("<s>\n")  # Start of <s> tag
            # Das Transkript muss von "SPACE" tokens bereinigt werden, da diese problematisch bei der Verarbeitung sind
            unclean_doc = nlp(cleaned_trans)
            cleaned_doc = [token.text for token in unclean_doc if token.pos_ != "SPACE"]
            cleaned_text = " ".join(cleaned_doc)
            doc = nlp(cleaned_text)
            print(doc.text)
            index = 0
            while index < len(doc):
                curr_token = doc[index] if index < len(doc) else None
                next_token = doc[index + 1] if index + 1 < len(doc) else None
                second_next_token = doc[index + 2] if index + 2 < len(doc) else None
                third_next_token = doc[index + 3] if index + 3 < len(doc) else None
                print(f'"Currently processing video with ID: {meta["video_id"]} '
                      f'and token: {curr_token.text}___{curr_token.pos_} at index: {index}"')
                if curr_token.text in ["ne", "n"]:
                    # Die Fälle in denen eine vollständige Negation vorliegt
                    # (ne/n' + PRON + VERB + NEG-ADV oder ne/n' + VERB + NEG-ADV)
                    # NOUN wird inkludiert um Taggingfehlern zuvorzukommen (siehe paper)
                    if next_token and second_next_token and (
                            (next_token.pos_ in ["PRON", "PUNCT"] and second_next_token.pos_ in ["VERB", "AUX",
                                                                                                 "NOUN"])):
                        f.write(
                            f'<negation full="true" negationParticle="{curr_token.text}">{curr_token.text} {next_token.text} {second_next_token.text} '
                            f'{third_next_token.text}</negation>')
                        index += 4
                    # Negation ohne Pronomen
                    elif next_token and (next_token.pos_ in ["VERB", "AUX", "NOUN", "PUNCT"]):
                        f.write(
                            f'<negation full="true" negationParticle="{curr_token.text}">{curr_token.text} {next_token.text} '
                            f'{second_next_token.text}</negation>')
                        index += 3
                    # Das "ne" erscheint direkt gefolgt von "pas". Wird als full-negation betrachtet
                    elif next_token and (next_token.lemma_ in negator_words):
                        f.write(
                            f'<negation full="true" negationParticle="{curr_token.text}">{curr_token.text} {next_token.text} '
                            f'{second_next_token.text}</negation>')
                        index += 3
                    # Zweig um mögliche Fehlausführung des Skripts durch
                    # nicht abgefangene Fälle zu verhindern (mindert die Datenqualität)
                    else:
                        f.write(f'{curr_token.text} ')
                        index += 1
                # Keine "volle" Negation. Es gibt kein vorangestelltes "ne" bzw. "n'".
                # Ob es ein next_token gibt muss geprüft werden
                elif curr_token.pos_ in ["VERB"] and (next_token and next_token.lemma_ in negator_words):
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
