#-------------------------------------------------------------------------------
# Name:        __init__.py
# Purpose:     Registering environment for SaRLVision.
#
# Author:      Matthias Bartolo <matthias.bartolo@ieee.org>
#
# Created:     February 24, 2024
# Copyright:   (c) Matthias Bartolo 2024-
# Licence:     All rights reserved
#-------------------------------------------------------------------------------
from gymnasium.envs.registration import register

# Registering the environments
register(
    id='DetectionEnv-v0',
    entry_point='SaRLVision.env:DetectionEnv',
    kwargs={"env_config": {'dataset': None}} # Normal environment (for spcifi single image input)
)

register(
    id='DetectionEnv-v0-Train',
    entry_point='SaRLVision.env:DetectionEnv',
    kwargs={"env_config": {'dataset': 'PascalVOC2007_2012Dataset', 'dataset_image_set': 'train', 'dataset_year': '2007+2012'}} # Training environment
)

register(
    id='DetectionEnv-v0-Test',
    entry_point='SaRLVision.env:DetectionEnv',
    kwargs={"env_config": {'dataset': 'PascalVOC2007_2012Dataset', 'dataset_image_set': 'test', 'dataset_year': '2007'}} # Testing environment
)

register(
    id='DetectionEnv-v0-Val',
    entry_point='SaRLVision.env:DetectionEnv',
    kwargs={"env_config": {'dataset': 'PascalVOC2007_2012Dataset', 'dataset_image_set': 'val', 'dataset_year': '2007'}} # Validation environment
)

register(
    id='DetectionEnv-v0-View',
    entry_point='SaRLVision.env:DetectionEnv',
    kwargs={"env_config": {'dataset': 'PascalVOC2007_2012Dataset', 'dataset_image_set': 'test', 'dataset_year': '2007', 'render_mode': "human"}} # Display environment
)