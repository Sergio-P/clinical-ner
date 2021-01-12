import flair.data
import flair.models
import flair.embeddings
import gensim.models
import re
import numpy as np
import torch
import os 
import glob 
import codecs 

class W2vWordEmbeddings(flair.embeddings.TokenEmbeddings):
    def __init__(self, embeddings):
        self.name = embeddings
        self.static_embeddings = False
        self.precomputed_word_embeddings = (
            gensim.models.KeyedVectors.load_word2vec_format(
                embeddings, binary=False, limit=100000
            )
        )
        self.__embedding_length = self.precomputed_word_embeddings.vector_size
        super().__init__()

    @property
    def embedding_length(self):
        return self.__embedding_length

    def _add_embeddings_internal(self, sentences):
        for i, sentence in enumerate(sentences):
            for token, token_idx in zip(sentence.tokens, range(len(sentence.tokens))):
                token = token
                if token.text in self.precomputed_word_embeddings:
                    word_embedding = self.precomputed_word_embeddings[token.text]
                elif token.text.lower() in self.precomputed_word_embeddings:
                    word_embedding = self.precomputed_word_embeddings[
                        token.text.lower()
                    ]
                elif (
                    re.sub("\d", "#", token.text.lower())
                    in self.precomputed_word_embeddings
                ):
                    word_embedding = self.precomputed_word_embeddings[
                        re.sub("\d", "#", token.text.lower())
                    ]
                elif (
                    re.sub("\d", "0", token.text.lower())
                    in self.precomputed_word_embeddings
                ):
                    word_embedding = self.precomputed_word_embeddings[
                        re.sub("\d", "0", token.text.lower())
                    ]
                else:
                    word_embedding = np.zeros(self.embedding_length, dtype="float")
                word_embedding = torch.FloatTensor(word_embedding)
                token.set_embedding(self.name, word_embedding)
        return sentences

def get_token_label(token):
    return token.get_labels("ner")[0].value


def annotate_text(text, model):
    sentence = flair.data.Sentence(text)
    model.predict(sentence)
    return sentence


def get_sentence_labels(sentence):
    labels = []
    for token in sentence.tokens:
        labels.append(get_token_label(token))
    return labels


def get_sentence_tokens(sentence):
    tokens = []
    for token in sentence.tokens:
        tokens.append(token.text)
    return tokens


def annotate_text_as_dict(text, model):
    sentence = annotate_text(text, model)
    raw_text = sentence.to_original_text()
    tokens = get_sentence_tokens(sentence)
    labels = get_sentence_labels(sentence)
    entities = get_sentence_entities(sentence)
    tagged_string = sentence.to_tagged_string()
    response = {
        "text": raw_text,
        "tokens": tokens,
        "labels": labels,
        "entities": entities,
        "tagged_string": tagged_string,
    }
    return response


def get_sentence_entities(sentence):
    entities = []
    for i, span in enumerate(sentence.get_spans()):
        entities.append(
            [f"T{i + 1}", span.labels[0].value, [[span.start_pos, span.end_pos]]]
        )
    return entities


def tag_referrals(model_folder, referrals_folder, ann_folder):
    # Load models
    models = [flair.models.SequenceTagger.load(model_path) for model_path in glob.iglob(f'{model_folder}*.pt')]
    print(f'El tiempo que tarda en cargar los modelos es: {time.time() - models_time} segundos.')
    # Annotate files
    for text_path in glob.iglob(f'{referrals_folder}*.txt'):
        filename = os.path.basename(text_path).split('.')[0]
        text = codecs.open(text_path, 'r', 'utf-8').read()
        ann = codecs.open(f'{ann_folder}{filename}.ann', 'w', 'utf-8')
        for model in models:
            result = annotate_text_as_dict(text, model)
            for entity in result['entities']:
                label_id = entity[0]
                label_type = entity[1]
                label_start_idx = entity[2][0][0]
                label_end_idx = entity[2][0][1]
                label_text = result['text'][label_start_idx:label_end_idx]
                ann.write(f'{label_id} {label_type} {label_start_idx} {label_end_idx} {label_text} \n')
        ann.close()