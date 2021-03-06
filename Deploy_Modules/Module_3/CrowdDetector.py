"""
Automatically generated by Colaboratory.
Original file is located at
    https://colab.research.google.com/drive/1r3VFkzSPd4HcqUCK0aaBwOYLXun9QS09
"""

import os
import glob
import json
import shutil
import numpy as np
from scipy.ndimage.filters import gaussian_filter
#from tqdm import tqdm
from matplotlib import cm as CM
from torch.utils.data import Dataset
import cv2
import torch
import torch.nn as nn
import random
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

class MCNN(nn.Module):
    
    '''
    Implementation of Multi-column CNN for crowd counting
    '''
    
    def __init__(self,load_weights=False):
        super(MCNN,self).__init__()

        self.branch1=nn.Sequential(
            nn.Conv2d(3,16,9,padding=4),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(16,32,7,padding=3),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32,16,7,padding=3),
            nn.ReLU(inplace=True),
            nn.Conv2d(16,8,7,padding=3),
            nn.ReLU(inplace=True)
        )

        self.branch2=nn.Sequential(
            nn.Conv2d(3,20,7,padding=3),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(20,40,5,padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(40,20,5,padding=2),
            nn.ReLU(inplace=True),
            nn.Conv2d(20,10,5,padding=2),
            nn.ReLU(inplace=True)
        )

        self.branch3=nn.Sequential(
            nn.Conv2d(3,24,5,padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(24,48,3,padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(48,24,3,padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(24,12,3,padding=1),
            nn.ReLU(inplace=True)
        )

        self.fuse=nn.Sequential(nn.Conv2d(30,1,1,padding=0))

        if not load_weights:
            self._initialize_weights()

    def forward(self,img_tensor):
        x1=self.branch1(img_tensor)
        x2=self.branch2(img_tensor)
        x3=self.branch3(img_tensor)
        x=torch.cat((x1,x2,x3),1)
        x=self.fuse(x)
        return x

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, std=0.01)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

class testCrowdDataset(Dataset):
    '''
    crowdDataset
    '''
    def __init__(self,img_root,gt_downsample=1):
        self.img_root=img_root
        self.gt_downsample=gt_downsample

        self.img_names=[filename for filename in os.listdir(img_root) \
                           if os.path.isfile(os.path.join(img_root,filename))]
        self.n_samples=len(self.img_names)

    def __len__(self):
        return self.n_samples

    def __getitem__(self,index):
        assert index <= len(self), 'index range error'
        img_name=self.img_names[index]
        img=plt.imread(os.path.join(self.img_root,img_name))

        if len(img.shape)==2: # expand grayscale image to three channel.
            img=img[:,:,np.newaxis]
            img=np.concatenate((img,img,img),2)

        if self.gt_downsample>1: # to downsample image and density-map to match deep-model.
            ds_rows=int(img.shape[0]//self.gt_downsample)
            ds_cols=int(img.shape[1]//self.gt_downsample)
            img = cv2.resize(img,(ds_cols*self.gt_downsample,ds_rows*self.gt_downsample))
            img=img.transpose((2,0,1)) # convert to order (channel,rows,cols)
        
        img_tensor=torch.tensor(img,dtype=torch.float)
        return img_tensor

class CrowdCounter:
 
    def make_backup(self):
        # shutil.copytree('/content/sample_data/test_image', './backup_images')
        from distutils.dir_util import copy_tree
        fromDirectory = '/test'
        toDirectory = './backup_images'
        copy_tree(fromDirectory, toDirectory)

    
    def predict_count(self,img_root,model_param_path):
        '''
        Predict the number of people in the input image.
        img_root: the root of test image data.
        model_param_path: the path of specific mcnn parameters.
        '''
        device=torch.device("cuda")
        mcnn=MCNN().to(device)
        mcnn.load_state_dict(torch.load(model_param_path))
        dataset = testCrowdDataset(img_root,4)
        dataloader=torch.utils.data.DataLoader(dataset,batch_size=1,shuffle=False)
        mcnn.eval()
        mae=0
        people_count = [] #list to store count of people in an image
        with torch.no_grad():
            for i,(img) in enumerate(dataloader):
                img=img.to(device)

                # forward propagation
                et_dmap=mcnn(img)
                people_count.append(round(float(et_dmap.data.sum())))
                del img,et_dmap
        return people_count        

    def FindCID(self):

        # if not os.path.exists('./backup_images'):
        # os.mkdir('./backup_images')
        
        self.make_backup()
        people_count = [] #list to store count of people in an image
        threshold = 20 # Set a threshold for the number of people allowed
        torch.backends.cudnn.enabled=False
        img_root='/test'
        # getting image names from folder
        img_nam = [filename for filename in os.listdir(img_root) \
                              if os.path.isfile(os.path.join(img_root,filename))]
        camera_id = [] #list to store camera Ids
        for img in img_nam:
            cid = img.split('_')
            camera_id.append(cid[0])

        model_param_path='/checkpoints/epoch_20.param'
        people_count = self.predict_count(img_root,model_param_path)    

        report_camera_id = [] #final list of Camera IDs where rules have been violated
        for i in range(len(people_count)):
          if people_count[i] > threshold :
            t = people_count[i],camera_id[i]
            report_camera_id.append(t)
            
        # for x in report_camera_id: # print camera IDs
        #   print(x)
        
        # Remove the image files from the folder
        files = glob.glob('/test/*') 
        for f in files:
          os.remove(f)

        return report_camera_id


#Running the model
#def GetList():
cc = CrowdCounter()
temp=cc.FindCID()
print(temp)



