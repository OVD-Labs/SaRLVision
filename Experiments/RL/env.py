import cv2
import gymnasium as gym
import numpy as np
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
from torch.autograd import Variable
from utils import *
from models import *

class DetectionEnv(gym.Env):
    def __init__(self, image, original_image, target_box, max_steps=500, alpha=0.2, nu=3.0, threshold=0.5, feature_extractor=VGG16FeatureExtractor(), target_size=VGG16_TARGET_SIZE):
        """
            Constructor of the DetectionEnv class.

            Input:
                - Image
                - Original image
                - Target bounding box
                - Maximum number of steps
                - Alpha
                - Nu
                - Threshold
                - Feature extractor
                - Target size

            Output:
                - Environment
        """
        super(DetectionEnv, self).__init__()
        # Initializing image, the original image which will be used as a visualisation, the target bounding box, the height and the width of the image.
        self.image = image
        self.original_image = original_image
        self.target_box = target_box
        self.height = image.shape[0]
        self.width = image.shape[1]
        self.target_size = target_size

        # Initializing the actions history and the number of episodes.
        self.actions_history = []
        self.num_episodes = 0
        self.actions_history += [[100]*9]*20

        # Initializing the bounding box of the image.
        self.bbox = [0, 0, self.width, self.height]

        # Initializing the feature extractor and the transform method.
        self.feature_extractor = feature_extractor
        self.transform = transform_input(self.image, target_size)

        # Initializing the action space and the observation space.
        # Action space is 9 because we have 8 actions + 1 trigger action (move right, move left, move up, move down, make bigger, make smaller, make fatter, make taller, trigger).
        self.action_space = gym.spaces.Discrete(9)

        # Initializing the observation space.
        # Calculating the size of the feature vector and the history vector.
        feature_len = self.get_features(self.image).shape[0]
        history_len = len(self.actions_history)
        # The observation space will be the features of the image concatenated with the history of the actions (size of the feature vector + size of the history vector).
        self.observation_space = gym.spaces.Box(
            low=0,
            high=1,
            shape=(feature_len + history_len,),
            dtype=np.float32
        )

        # Setting terminated and truncated to False.
        self.terminated = False
        self.truncated = False
        
        # Initializing the maximum number of steps, the current step, the scaling factor of the reward, the reward of the trigger, the cumulative reward, the threshold, the actions history and the number of episodes.
        self.max_steps = max_steps
        self.step_count = 0
        self.alpha = alpha
        self.nu = nu # Reward of Trigger
        self.cumulative_reward = 0
        self.truncated = False
        self.threshold = threshold

    def calculate_reward(current_state, previous_state, target_box, reward_function=iou):
        """
            Calculating the reward.

            Input:
                - Current state
                - Previous state
                - Target bounding box
                - Reward function

            Output:
                - Reward
        """
        # Calculating the IoU between the current state and the target bounding box.
        iou_current = reward_function(current_state, target_box)

        # Calculating the IoU between the previous state and the target bounding box.
        iou_previous = reward_function(previous_state, target_box)

        # Calculating the reward.
        reward = iou_current - iou_previous

        # If the reward is smaller than 0, we return -1 else we return 1.
        if reward <= 0:
            return -1
        
        # Returning 1.
        return 1
    
    def calculate_trigger_reward(self, current_state, target_box, reward_function=iou):
        """
            Calculating the reward.

            Input:
                - Current state
                - Target bounding box
                - Reward function

            Output:
                - Reward
        """
        # Calculating the IoU between the current state and the target bounding box.
        iou_current = reward_function(current_state, target_box)

        # Calculating the reward.
        reward = iou_current

        # If the reward is larger than the threshold, we return trigger reward else we return -1*trigger reward.
        if reward >= self.threshold:
            return self.nu
        
        # Returning -1*trigger reward.
        return -1*self.nu
    
    def get_features(self, image, dtype=FloatTensor):
        """
            Getting the features of the image.

            Input:
                - Image

            Output:
                - Features of the image
        """
        # Transforming the image.
        image = transform_input(image, target_size=self.target_size)

        # Retrieving the features of the image.
        features = self.feature_extractor(image.unsqueeze(0))

        # Returning the features.
        return features

    def get_state(self, dtype=FloatTensor):
        """
            Getting the state of the environment.

            Output:
                - State of the environment
        """
        # Transforming the image.
        image = transform_input(self.image, target_size=self.target_size)

        # Retrieving the features of the image.
        features = self.get_features(image)

        # Transposing the features.
        features = features.view(1, -1)

        # Flattenning the action history.
        action_history = self.actions_history.view(1,-1).type(dtype)

        # Concatenating the features and the action history.
        state = torch.cat((features, action_history), 1)

        # Returning the state.
        return state
    
    def update_history(self, action):
        """
            Function that updates the history of the actions by adding the last one.

            Input:
                - Last action performed

            Output:
                - History of the actions
        """
        # Creating the action vector.
        action_vector = torch.zeros(9)

        # Setting the action vector.
        action_vector[action] = 1

        # Retrieving the size of the history vector.
        size_history_vector = len(torch.nonzero(self.actions_history))

        # If the size of the history vector is smaller than 9, we add the action vector to the history vector.
        if size_history_vector < 9:
            self.actions_history[size_history_vector][action] = 1
        else:
            # Else we shift the history vector by one and we add the action vector to the history vector.
            for i in range(8,0,-1):
                self.actions_history[i][:] = self.actions_history[i-1][:]
            self.actions_history[0][:] = action_vector[:]

        # Returning the history of the actions.
        return self.actions_history
    
    def transform_action(self, action):
        """
            Function that applies the action to the image.

            Actions:
                - 0: Move right
                - 1: Move left
                - 2: Move up
                - 3: Move down
                - 4: Make bigger
                - 5: Make smaller
                - 6: Make fatter
                - 7: Make taller

            Input:
                - Action to apply

            Output:
                - Bounding box of the image
        
        """
        # Retrieving the bounding box of the image.
        bbox = self.bbox

        # Retrieving the coordinates of the bounding box.
        xmin, xmax, ymin, ymax = bbox[0], bbox[2], bbox[1], bbox[3]

        # Calculating the alpha_h and alpha_w mentioned in the paper.
        alpha_h = self.alpha * (  ymax - ymin )
        alpha_w = self.alpha * (  xmax - xmin )

        # If the action is 0, we move the bounding box to the right.
        if action == 0:
            xmin += alpha_w
            xmax += alpha_w
        # If the action is 1, we move the bounding box to the left. 
        elif action == 1:
            xmin -= alpha_w
            xmax -= alpha_w
        # If the action is 2, we move the bounding box up.
        elif action == 2:
            ymin -= alpha_h
            ymax -= alpha_h
        # If the action is 3, we move the bounding box down.
        elif action == 3:
            ymin += alpha_h
            ymax += alpha_h
        # If the action is 4, we make the bounding box bigger.
        elif action == 4:
            ymin -= alpha_h
            ymax += alpha_h
            xmin -= alpha_w
            xmax += alpha_w
        # If the action is 5, we make the bounding box smaller.
        elif action == 5:
            ymin += alpha_h
            ymax -= alpha_h
            xmin += alpha_w
            xmax -= alpha_w
        # If the action is 6, we make the bounding box fatter.
        elif action == 6:
            ymin += alpha_h
            ymax -= alpha_h
        # If the action is 7, we make the bounding box taller.
        elif action == 7:
            xmin += alpha_w
            xmax -= alpha_w

        # Returning the bounding box, whilst ensuring that the bounding box is within the image.
        return [self.rewrap(xmin, self.width), self.rewrap(ymin, self.height), self.rewrap(xmax, self.width), self.rewrap(ymax, self.height)]

    def rewrap(self, coordinate, size):
        """
            Function that rewrap the coordinate if it is out of the image.

            Input:
                - Coordinate to rewrap
                - Size of the image

            Output:
                - Rewrapped coordinate
        """
        return min(max(0, coordinate), size)
    
    def get_info(self):
        """
            Function that returns the information of the environment.

            Output:
                - Information of the environment
        """
        return {
            'target_box': self.target_box,
            'height': self.height,
            'width': self.width,
            'target_size': self.target_size,
            'max_steps': self.max_steps,
            'step_count': self.step_count,
            'alpha': self.alpha,
            'nu': self.nu,
            'cumulative_reward': self.cumulative_reward,
            'threshold': self.threshold,
            'actions_history': self.actions_history,
            'num_episodes': self.num_episodes,
            'bbox': self.bbox,
            'feature_extractor': self.feature_extractor,
            'transform': self.transform,
            'iou': iou(self.bbox, self.target_box),
            'recall': recall(self.bbox, self.target_box),
        }
    
    def reset(self, image, original_image, target_box, max_steps=500, alpha=0.2, nu=3.0, threshold=0.5, feature_extractor=VGG16FeatureExtractor(), target_size=VGG16_TARGET_SIZE):
        """
            Function that resets the environment.

            Input:
                - Image
                - Original image
                - Target bounding box
                - Maximum number of steps
                - Alpha
                - Nu
                - Threshold
                - Feature extractor
                - Target size

            Output:
                - State of the environment
        """
        # Initializing image, the original image which will be used as a visualisation, the target bounding box, the height and the width of the image.
        self.image = image
        self.original_image = original_image
        self.target_box = target_box
        self.height = image.shape[0]
        self.width = image.shape[1]
        self.target_size = target_size
        
        # Initializing the maximum number of steps, the current step, the scaling factor of the reward, the reward of the trigger, the cumulative reward, the threshold, the actions history and the number of episodes.
        self.max_steps = max_steps
        self.step_count = 0
        self.alpha = alpha
        self.nu = nu # Reward of Trigger
        self.cumulative_reward = 0
        self.truncated = False
        self.threshold = threshold

        # Initializing the actions history and the number of episodes.
        self.actions_history = []
        self.num_episodes = 0
        self.actions_history += [[100]*9]*20

        # Initializing the bounding box of the image.
        self.bbox = [0, 0, self.width, self.height]

        # Initializing the feature extractor and the transform method.
        self.feature_extractor = feature_extractor
        self.transform = transform_input(self.image, target_size)

        # Returning the state of the environment.
        return self.get_state()
    
    def step(self, action):
        """
            Function that performs an action on the environment.

            Input:
                - Action to perform

            Output:
                - State of the environment
                - Reward of the action
                - Whether the episode is finished or not
                - Information of the environment
        """
        # Updating the history of the actions.
        self.update_history(action)

        # Declaring the reward.
        reward = 0

        # Checking the action type and applying the action to the image (transform action).
        if action < 8:
            self.bbox = self.transform_action(action)
            reward = self.calculate_reward(self.bbox, self.target_box)
        else:
            reward = self.calculate_trigger_reward(self.bbox, self.target_box)
            self.terminated = True

        # Calculating the cumulative reward.
        self.cumulative_reward += reward

        # Incrementing the step count.
        self.step_count += 1

        # Checking if the episode is finished or truncated.
        if not self.terminated or not self.truncated:
            # Checking if the episode is finished.
            self.terminated = self.step_count >= self.max_steps

            # Checking if the episode is truncated.
            self.truncated = self.step_count >= self.max_steps

        # If the episode is finished, we increment the number of episodes.
        if self.terminated or self.truncated:
            self.num_episodes += 1

        # Returning the state of the environment, the reward, whether the episode is finished or not, whether the episode is truncated or not and the information of the environment.
        return self.get_state(), reward, self.terminated, self.truncated, self.get_info()
    
    def render(self, mode='image', do_display=False):
        """
            Function that renders the environment.

            Input:
                - Mode of rendering
                - Whether to display the image or not

            Output:
                - Image of the environment
        """
        # Retrieving bounding box coordinates.
        xmin, ymin, xmax, ymax = self.bbox

        # Checking the mode of rendering.
        if mode == 'image':
            # Creating a copy of the original image.
            image = self.original_image.copy()

            # Drawing the bounding box on the image.
            cv2.rectangle(image, (xmin, ymin), (xmax, ymax), (0, 255, 0), 3)

            # Plotting the image.
            if do_display:
                self.plot_img(image)

            # Returning the image.
            return image
        elif mode == 'bbox':
            # Creating a black image from the original image.
            image = np.zeros_like(self.original_image)

            # Drawing the bounding box on the image.
            cv2.rectangle(image, (xmin, ymin), (xmax, ymax), (0, 255, 0), cv2.FILLED)

            # Plotting the image.
            if do_display:
                self.plot_img(image)

            # Returning the image.
            return image
        elif mode == 'heatmap':
            # Creating a black image.
            image = np.zeros_like(self.original_image)

            # Drawing the bounding box on the image.
            cv2.rectangle(image, (xmin, ymin), (xmax, ymax), (0, 255, 0), cv2.FILLED)

            # Creating the heatmap.
            heatmap = cv2.applyColorMap(image, cv2.COLORMAP_JET)

            # Plotting the image.
            if do_display:
                self.plot_img(heatmap)

            # Returning the image.
            return heatmap
        
    def plot_img(self, image):
        """
            Function that plots the image.

            Input:
                - Image to plot
        """
        # Plotting the image.
        plt.figure(figsize=(10, 7))
        plt.imshow(image, cmap='gray')
        plt.axis('off')
        plt.show()
        
    def close(self):
        """
            Function that closes the environment.
        """
        gym.Env.close(self)
        pass

    # def resize_bbox(bbox, size):
    #     """
    #         Function that resizes the bounding box.

    #         Input:
    #             - Bounding box
    #             - Size of the image

    #         Output:
    #             - Resized bounding box
    #     """
    #     # Retrieving the coordinates of the bounding box.
    #     xmin, ymin, xmax, ymax = bbox[0], bbox[1], bbox[2], bbox[3]

    #     # Calculating the new coordinates of the bounding box.
    #     xmin = int(xmin * size[0])
    #     ymin = int(ymin * size[1])
    #     xmax = int(xmax * size[0])
    #     ymax = int(ymax * size[1])

    #     # Returning the new bounding box.
    #     return [xmin, ymin, xmax, ymax]
