#-------------------------------------------------------------------------------
# Name:        models.py
# Purpose:     Defining models for SaRLVision.
#
# Author:      Matthias Bartolo <matthias.bartolo@ieee.org>
#
# Created:     February 24, 2024
# Copyright:   (c) Matthias Bartolo 2024-
# Licence:     All rights reserved
#-------------------------------------------------------------------------------
import math
import torch
import torch.nn as nn
from torch.nn.init import  uniform_
import torch.nn.functional as F
import torchvision
import torchvision.transforms as transforms
from torchvision.models import vgg16, VGG16_Weights, resnet50, ResNet50_Weights, mobilenet_v2, MobileNet_V2_Weights
from keras.applications.vgg16 import VGG16, decode_predictions, preprocess_input
from keras.applications.resnet_v2 import ResNet50V2, decode_predictions, preprocess_input
from keras.applications.mobilenet_v2 import MobileNetV2, decode_predictions, preprocess_input
from keras.applications.efficientnet_v2 import EfficientNetV2, decode_predictions, preprocess_input
from keras.applications.xception import Xception, decode_predictions, preprocess_input
from keras.applications.inception_v3 import InceptionV3, decode_predictions, preprocess_input

from SaRLVision.utils import device

import warnings
warnings.filterwarnings("ignore")

"""
    Defining the target size of the input image for each model.
"""
VGG16_TARGET_SIZE = (224, 224)
RESNET50_TARGET_SIZE = (224, 224)
MOBILENETV2_TARGET_SIZE = (224, 224)
EFFICIENTNETV2_TARGET_SIZE = (224, 224)
XCEPTION_TARGET_SIZE = (299, 299)
INCEPTIONV3_TARGET_SIZE = (299, 299)


"""
    VGG16 Feature Extractor (Feature Learning Model).
"""
class VGG16FeatureExtractor(nn.Module):
    def __init__(self):
        super(VGG16FeatureExtractor, self).__init__()
        self.vgg16_model = vgg16(weights=VGG16_Weights.DEFAULT).to(device) # Loading the pretrained model
        self.vgg16_model.eval() # Setting the model in evaluation mode to not do dropout.
        self.features = list(self.vgg16_model.children())[0] # Retrieving the first child of the model, which is typically the image feature extraction part of the model
        self.classifier = nn.Sequential(*list(self.vgg16_model.classifier.children())[:-2]) # Retrieving the image feature extraction part of the model, and removing the last two layers, which are typically the dropout and the last layer of the model

    def forward(self, x):# Forwarding the input through the model
        x = self.features(x) # Applying the image feature extraction part of the model
        return x
    
    
"""
    ResNet50 Feature Extractor (Feature Learning Model).
"""
class ResNet50FeatureExtractor(nn.Module):
    def __init__(self):
        super(ResNet50FeatureExtractor, self).__init__()
        self.resnet50_model = resnet50(weights=ResNet50_Weights.DEFAULT).to(device) # Loading the pretrained model
        self.resnet50_model.eval() # Setting the model in evaluation mode to not do dropout.
        self.features = nn.Sequential(*list(self.resnet50_model.children())[:-1])# Retrieving the image feature extraction part of the model, and removing the last layer of the model

    def forward(self, x):# Forwarding the input through the model
        x = self.features(x) # Applying the image feature extraction part of the model
        return x
    
    
"""
    MobileNetV2 Feature Extractor (Feature Learning Model).
"""
class MobileNetV2FeatureExtractor(nn.Module):
    def __init__(self):
        super(MobileNetV2FeatureExtractor, self).__init__()
        self.mobilenetv2 = mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT).to(device) # Loading the pretrained model
        self.mobilenetv2.eval() # Setting the model in evaluation mode to not do dropout.
        self.features = self.mobilenetv2.features  # Retrieving the first child of the model, which is typically the image feature extraction part of the model
    
    def forward(self, x):# Forwarding the input through the model
        x = self.features(x)  # Applying the image feature extraction part of the model
        return x


"""
    Method to transform the input image to the input of the model.
"""
def transform_input(image, target_size):
    """
        Transforming the input image to the input of the model.
        
        Args:
            image: The input image.
            target_size: The target size of the image.
            
        Returns:
            The transformed image.
    """
    transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize(target_size),
            transforms.ToTensor(),
    ])
    return transform(image)


"""
    Architecture of the Vanilla (Standard) DQN model.
"""
class DQN(nn.Module):
    """
    The DQN network that estimates the action-value function

    Args:
        ninputs: The number of inputs
        noutputs: The number of outputs

    Layers:
        1. Linear layer with ninputs neurons
        2. ReLU activation function
        3. Dropout layer with 0.2 dropout rate
        4. Linear layer with 1024 neurons
        5. ReLU activation function
        6. Dropout layer with 0.2 dropout rate
        7. Linear layer with 512 neurons
        8. ReLU activation function
        9. Dropout layer with 0.2 dropout rate
        10. Linear layer with 256 neurons
        11. ReLU activation function
        12. Dropout layer with 0.2 dropout rate
        13. Linear layer with 128 neurons
    """
    def __init__(self, ninputs, noutputs):
        super(DQN, self).__init__()
        self.classifier = nn.Sequential(
            nn.Linear(ninputs, 1024),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(1024, 512),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, noutputs)
        )

    def forward(self, X):
        # Forward pass
        return self.classifier(X)

    def __call__(self, X):
        return self.forward(X)


"""
    Architecture of the Dueling DQN model.
"""
class DuelingDQN(nn.Module):
    """
    The dueling DQN network that estimates the action-value function

    Args:
        ninputs: The number of inputs
        noutputs: The number of outputs

    Layers:
        1. Linear layer with ninputs neurons
        2. ReLU activation function
        3. Linear layer with 1024 neurons
        4. ReLU activation function
        5. Linear layer with 512 neurons
        6. ReLU activation function
        7. Linear layer with 256 neurons
        8. ReLU activation function
        
    Value Function:
        1. Linear layer with 128 neurons
        2. ReLU activation function
        3. Linear layer with 1 neuron

    Advantage Function:
        1. Linear layer with 128 neurons
        2. ReLU activation function
        3. Linear layer with noutputs neurons

    """
    def __init__(self, ninputs, noutputs):
        super(DuelingDQN, self).__init__()
        self.shared_layers = nn.Sequential(
            nn.Linear(ninputs, 1024),
            nn.ReLU(),
            nn.Linear(1024, 512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU()
        )
        
        self.valfunc = nn.Linear(128, 1)
        self.advfunc = nn.Linear(128, noutputs)

    def forward(self, X):
        # Forward pass through shared layers
        o = self.shared_layers(X)
        # Splitting the output into the value and advantage functions
        value = self.valfunc(o)
        adv = self.advfunc(o)
        # Returning the value and advantage functions combined into the Q function (Q = V + A - mean(A))
        return value + adv - adv.mean(dim=-1, keepdim=True)




# ------------------- Noisy DQN -------------------
class NoisyLinear(nn.Module):
    """
        The noisy linear layer that adds noise to the weights of the linear layer

        Args:
            in_size: The number of inputs
            out_size: The number of outputs

        Layers:
            1. Linear layer with in_size inputs and out_size outputs
            2. Linear layer with in_size inputs and out_size outputs
            3. Linear layer with out_size outputs
            4. Linear layer with out_size outputs
    """
    def __init__(self, in_size, out_size):
        super(NoisyLinear, self).__init__()
        # Defining the parameters of the layer as trainable parameters (weights and biases mu and sigma)
        self.w_mu = nn.Parameter(torch.empty((out_size, in_size)))
        self.w_sigma = nn.Parameter(torch.empty((out_size, in_size)))
        self.b_mu = nn.Parameter(torch.empty((out_size)))
        self.b_sigma = nn.Parameter(torch.empty((out_size)))

        # Creating the noise tensors for the weights and biases of the layer (w_epsilon and b_epsilon)
        uniform_(self.w_mu, -math.sqrt(3 / in_size), math.sqrt(3 / in_size))
        uniform_(self.b_mu, -math.sqrt(3 / in_size), math.sqrt(3 / in_size))

        # Initializing the noise tensors with the same shape as the weights and biases
        nn.init.constant(self.w_sigma, 0.017)
        nn.init.constant(self.b_sigma, 0.017)

    def forward(self, x, sigma=0.1): # Sigma Controls the amount of noise was 1 before
        # Forward pass through the layer
        if self.training: # If the model is in training mode, add noise to the weights and biases
            w_noise = torch.normal(0, sigma, size=self.w_mu.size())
            b_noise = torch.normal(0, sigma, size=self.b_mu.size())
            return F.linear(x, self.w_mu + self.w_sigma * w_noise, self.b_mu + self.b_sigma * b_noise)
        else:# If the model is in evaluation mode, return the mean of the weights and biases
            return F.linear(x, self.w_mu, self.b_mu)
        
class NoisyDQN(nn.Module):
    """
        The noisy DQN network that estimates the action-value function

        Args:
            ninputs: The number of inputs
            noutputs: The number of outputs

        Layers:
            1. Noisy linear layer with 64 neurons
            2. Tanh activation function
            3. Noisy linear layer with noutputs neurons
    """
    def __init__(self, ninputs, noutputs):
        super(NoisyDQN, self).__init__()
        self.a1 = NoisyLinear(ninputs, 1024)
        self.a2 = NoisyLinear(1024, noutputs)

    def forward(self, X):
        # Forward pass
        o = self.a1(X)
        o = torch.tanh(o)
        o = self.a2(o)
        return o

    def __call__(self, X):
        return self.forward(X)