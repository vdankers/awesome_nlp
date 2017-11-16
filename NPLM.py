import time
import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import nltk.corpus
from utils import get_w2i, load_glove_matrix

# Default settings, may be overwritten because of data used
CONTEXT_SIZE = 3
VOCABULARY_DIM = 40000
EMBEDDING_DIM = 50
ITER = 100


def encode_history(history, w2i):
    """
    Represent a history of words as a list of indices.
    """
    return [w2i[word] for word in history]


def evaluate(model, ngrams, w2i, i2w):
    """
    Evaluate a model on a data set.
    """
    correct = 0

    for history, continuation in ngrams:
        indices = encode_history(history, w2i)
        lookup_tensor = Variable(torch.LongTensor(indices))
        scores = model(lookup_tensor)
        predict = scores.data.numpy().argmax(axis=1)[0]
        # print(history, continuation, i2w[predict])

        if predict == w2i[continuation]:
            correct += 1

    return correct, len(ngrams), correct/len(ngrams)


class NPLM(nn.Module):
    """
    Neural Probabilistic Language Model, as described by Bengio (2003).
    """
    def __init__(self, context, vocab_dim, embed_dim, pretrained=None):
        super(NPLM, self).__init__()
        self.embeddings = nn.Embedding(vocab_dim, embed_dim)

        # Use pretrained weights, a numpy matrix of shape vocab_dim x embed_dim
        if pretrained is not None:
            self.embeddings.weight.data.copy_(torch.from_numpy(pretrained))
        self.linear1 = nn.Linear(context * embed_dim, 100)
        self.tanh = nn.Tanh()
        self.linear2 = nn.Linear(100, vocab_dim)

    def forward(self, inputs):
        embeds = self.embeddings(inputs).view((1, -1))
        out = self.tanh(self.linear1(embeds))
        return F.log_softmax(self.linear2(out))


def to_ngrams(sentences, history_size):
    """
    Extracts all n-grams from a list of sentences.
    """
    ngrams = []
    for s in sentences:
        for i in range(len(s)-history_size):
            ngrams.append((s[i:i+history_size], s[i+history_size]))
    return ngrams


if __name__ == "__main__":
    # Get corpus, word indices and ngrams for evaluation
    words = [word.lower() for word in nltk.corpus.treebank.words()]
    sentences = [
        [word.lower() for word in s] for s in nltk.corpus.treebank.sents()
        ]
    i2w, w2i = get_w2i(words)
    print("Done reading data.")
    ngrams = to_ngrams(sentences, CONTEXT_SIZE)
    train = ngrams[:-1000]
    test = ngrams[-1000:]
    print("Prepared n-grams for evaluation.")

    # Initialize word embeddings with 50d glove vectors
    embeddings_matrix = load_glove_matrix(w2i, "glove.6B/glove.6B.50d.txt")
    print("Done with reading in glove vectors.")

    VOCABULARY_DIM = len(w2i)
    EMBEDDING_DIM = len(embeddings_matrix[0, :])

    # Initalize the neural network
    model = NPLM(CONTEXT_SIZE, VOCABULARY_DIM, EMBEDDING_DIM, embeddings_matrix)
    print("Initalized the Neural Probabilistic Language Model.")
    print(model)
    optimizer = optim.SGD(params=model.parameters(), lr=1e-03, weight_decay=1e-5)

    for i in range(ITER):
        train_loss = 0.0
        start = time.time()

        for j, (history, continuation) in enumerate(train):
            # forward pass

            indices = encode_history(history, w2i)
            lookup_tensor = Variable(torch.LongTensor(indices))
            scores = model.forward(lookup_tensor)

            loss = nn.NLLLoss()
            target = Variable(torch.LongTensor([w2i[continuation]]))
            output = loss(scores, target)
            train_loss += output.data[0]

            # backward pass
            optimizer.zero_grad()
            model.zero_grad()
            output.backward()
            optimizer.step()

            if j % 1000 == 0:
                _, _, acc = evaluate(model, train, w2i, i2w)
                print("Epoch {}, iter {}, train acc={}".format(i, j, acc))

        print("loss: ", train_loss)
