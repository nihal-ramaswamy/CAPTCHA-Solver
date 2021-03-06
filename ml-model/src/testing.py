from google.colab import drive
drive.mount('/content/drive')

"""Imports, paths, defined variables"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from torchvision.models import resnet18

import cv2
import multiprocessing as mp

from google.colab.patches import cv2_imshow

data_path = "/content/drive/MyDrive/Colab Notebooks/Attempt2/CaptchaImages"
path_to_model = "/content/drive/MyDrive/Colab Notebooks/MixedDatasets/weights.pt"

rnn_hidden_size = 256
threshold = 99
dropout = 0.1
WIDTH = 200
HEIGHT = 50

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

"""Getting possible characters"""

letters = ['2',
 '3',
 '4',
 '5',
 '6',
 '7',
 '8',
 'b',
 'c',
 'd',
 'e',
 'f',
 'g',
 'm',
 'n',
 'p',
 'w',
 'x',
 'y']

vocabulary = ["-"] + letters
idx2char = {k:v for k,v in enumerate(vocabulary, start=0)}
char2idx = {v:k for k,v in idx2char.items()}
num_chars = len(char2idx)

"""Model"""

resnet = resnet18(pretrained=True)

class CRNN(nn.Module):
  def __init__(self, num_chars, dropout=dropout):    
    super(CRNN, self).__init__()
    self.num_chars = num_chars
    self.dropout = dropout

    # CNN Part 1
    self.cnn_p0 = nn.Sequential(nn.Conv2d(1, 3, kernel_size = (3,6), stride = 1, padding = 1), nn.BatchNorm2d(3), nn.ReLU(inplace = True))
    
    # CNN Part 2
    resnet_modules = list(resnet.children())[:-3]
    self.cnn_p1 = nn.Sequential(*resnet_modules)
    
    # CNN Part 3
    self.cnn_p2 = nn.Sequential(nn.Conv2d(256, 256, kernel_size = (3,6), stride = 1, padding = 1), nn.BatchNorm2d(256), nn.ReLU(inplace = True))
    
    self.linear1 = nn.Linear(1024, 256)
    
    # # RNN
    self.rnn1 = nn.GRU(input_size = rnn_hidden_size, hidden_size = rnn_hidden_size, bidirectional = True, batch_first = True)
    # self.rnn2 = nn.GRU(input_size = rnn_hidden_size, hidden_size = rnn_hidden_size, bidirectional = True, batch_first = True)
    self.linear2 = nn.Linear(256, num_chars)
        
        
  def forward(self, batch):
    batch = self.cnn_p0(batch)
    batch = self.cnn_p1(batch)
    batch = self.cnn_p2(batch) # [batch_size, channels, height, width]
    
    batch = batch.permute(0, 3, 1, 2) # [batch_size, width, channels, height]
      
    batch_size = batch.size(0)
    T = batch.size(1)
    batch = batch.view(batch_size, T, -1) # [batch_size, T==width, num_features==channels*height]
    batch = self.linear1(batch)
    
    batch, hidden = self.rnn1(batch)
    feature_size = batch.size(2)
    batch = batch[:, :, :feature_size//2] + batch[:, :, feature_size//2:]
    # batch, hidden = self.rnn2(batch)

    batch = self.linear2(batch)
    batch = batch.permute(1, 0, 2) # [T==10, batch_size, num_classes==num_features]
    
    return batch

model = torch.load(path_to_model)
model.eval()

"""Defining required functions"""

def decode_predictions(text_batch_logits):

  text_batch_tokens = F.softmax(text_batch_logits, 2).argmax(2) # [T, batch_size]
  text_batch_tokens = text_batch_tokens.numpy().T # [batch_size, T]

  text_batch_tokens_new = []
  for text_tokens in text_batch_tokens:
    text = [idx2char[idx] for idx in text_tokens]
    text = "".join(text)
    text_batch_tokens_new.append(text)

  return text_batch_tokens_new

def remove_duplicates(text):
  if len(text) > 1:
    letters = [text[0]] + [letter for idx, letter in enumerate(text[1:], start=1) if text[idx] != text[idx-1]]
  elif len(text) == 1:
    letters = [text[0]]
  else:
    return ""
  return "".join(letters)

def correct_prediction(word):
  parts = word.split("-")
  parts = [remove_duplicates(part) for part in parts]
  corrected_word = "".join(parts)
  return corrected_word

def test_image(image_path, threshold, kernel, model):
  image = cv2.imread(image_path)
  cv2_imshow(image)
  image = cv2.cvtColor(image.copy(), cv2.COLOR_BGR2GRAY)
  image = cv2.resize(image, (WIDTH, HEIGHT))
  ret, image = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY_INV)
  image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)

  transform_ops = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mean=(0.456), std=(0.2245))])
  image = transform_ops(image)
  image = image.unsqueeze(1)
  return correct_prediction(decode_predictions(model(image.to(device)).cpu())[0])

"""Testing Image"""

INPUT_IMAGE = "/content/drive/MyDrive/Colab Notebooks/MixedDatasets/CaptchaImages/226md.png"

test_image(INPUT_IMAGE, 99, kernel, model)