# encoding: utf8
__author__ = "alberto.rincon.borreguero@gmail.com"
"""
Preprocessing data functions and other utilities.
"""

import imageio
import pandas as pd
import numpy as np
import os
import logging
logging.basicConfig(level=logging.INFO)
import warnings
warnings.filterwarnings("ignore")

from tqdm import tqdm
from skimage.transform import resize
from keras.preprocessing.image import ImageDataGenerator, array_to_img, img_to_array, load_img

from keras.models import Model, load_model
from keras.layers import Dense, Input, merge, Dropout, Lambda, BatchNormalization, LeakyReLU, PReLU
from keras.constraints import maxnorm
from keras.optimizers import Adam, SGD
from keras.layers.convolutional import Conv2D, UpSampling2D, MaxPooling2D
from keras.preprocessing.image import ImageDataGenerator
from keras.backend import tf
from keras.initializers import glorot_uniform


def get_data(data_info="train",folder=None, resolution=(128,128)):
    """
    Itera sobre cada carpeta que contiene mascaras e imagenes completas. Unicamente devuelve arrays de numpy
    con las imagenes completas.
    """
    logging.info("Obteniendo datos de %s" %data_info)
    logging.info("Ruta: %s" %folder)
    images = list()
    id_list = list(os.walk(folder))[0][1]
    [images.append(img_to_array(load_img("{folder}/{uid}/images/{uid}.png".format(folder=folder,uid=img_id)))) for img_id in tqdm(id_list)]
    logging.info("Redimensionando imágenes a {resolution}".format(resolution=resolution))
    images = [resize(image.astype(np.uint8),resolution) for image in tqdm(images) ]
    res = np.asarray(images, dtype=object)
    return res

def get_masks(mask_path, resolution=(128,128)):
    """
    Itera de forma individual sobre cada máscara y las agrupa por imagen completa para generar una mascara
    completa de todos los nucleos celulares de una unica imagen completa.
    Las mascaras son convertidas a binario, siendo el valor del pixel 0 si no
    se corresponde con un nucleo, y 1 en caso de que si.
    """
    logging.info("Cargando mascaras en array de numpy")
    logging.info("Ruta %s" %mask_path)
    id_list = list(os.walk(mask_path))[0][1]
    labeled_images = list()
    for id_ in tqdm(id_list):
        img_dir = "{path}/{id_}/masks/".format(path=mask_path, id_=id_)
        total_mask = np.zeros(resolution)
        for mask in list(os.walk(img_dir))[0][2]:
            img_mask = imageio.imread(img_dir + mask, pilmode='L')#.astype(np.float32)
            img_mask_resized = resize(img_mask, resolution).astype(np.float32)
            total_mask = total_mask + img_mask_resized
        total_mask[total_mask > 0] = 1
        labeled_images.append(total_mask)
    res = np.asarray(labeled_images, dtype=object).reshape(-1,resolution[0],resolution[1],1)
    return res

def get_model():
  """
  Basado en la arquitectura de la U-Net. Los kenerls de convolucion han sido reducidos
  porque las imagenes de nuestro conjunto de entrenamiento tienen aproximadamente
  la mitad de la resolucion de los ejempos de U-Net.
  """
  inputs = Input((128, 128,3))

  conv1 = Conv2D(64, 3, padding = 'same', kernel_initializer = 'he_normal')(inputs) # 64 : 4 = 16
  conv1 = LeakyReLU(alpha=0.3)(conv1)
  conv1 = Conv2D(64, 3, padding = 'same', kernel_initializer = 'he_normal')(conv1)  # ""
  conv1 = LeakyReLU(alpha=0.3)(conv1)
  pool1 = MaxPooling2D(pool_size=(2, 2))(conv1)

  conv2 = Conv2D(128, 3, padding = 'same', kernel_initializer = 'he_normal')(pool1) # 128 : 4 = 32
  conv2 = LeakyReLU(alpha=0.3)(conv2)
  conv2 = Conv2D(128, 3, padding = 'same', kernel_initializer = 'he_normal')(conv2) # ""
  conv2 = LeakyReLU(alpha=0.3)(conv2)
  pool2 = MaxPooling2D(pool_size=(2, 2))(conv2)

  conv3 = Conv2D(256, 3, padding = 'same', kernel_initializer = 'he_normal')(pool2)# 256 : 4 = 64
  conv3 = LeakyReLU(alpha=0.3)(conv3)
  conv3 = Conv2D(256, 3, padding = 'same', kernel_initializer = 'he_normal')(conv3)
  conv3 = LeakyReLU(alpha=0.3)(conv3)
  pool3 = MaxPooling2D(pool_size=(2, 2))(conv3)
  conv4 = Conv2D(512, 3, padding = 'same', kernel_initializer = 'he_normal')(pool3)# 512 : 4 = 128
  conv4 = LeakyReLU(alpha=0.3)(conv4)
  conv4 = Conv2D(512, 3, padding = 'same', kernel_initializer = 'he_normal')(conv4)
  conv4 = LeakyReLU(alpha=0.3)(conv4)
  drop4 = Dropout(0.5)(conv4)
  pool4 = MaxPooling2D(pool_size=(2, 2))(drop4)

  conv5 = Conv2D(1024, 3,padding = 'same', kernel_initializer = 'he_normal')(pool4)
  conv5 = LeakyReLU(alpha=0.3)(conv5)
  conv5 = Conv2D(1024, 3,padding = 'same', kernel_initializer = 'he_normal')(conv5)
  conv5 = LeakyReLU(alpha=0.3)(conv5)
  drop5 = Dropout(0.5)(conv5)

  up6 = Conv2D(512, 2, padding = 'same', kernel_initializer = 'he_normal')(UpSampling2D(size = (2,2))(drop5))
  up6 = LeakyReLU(alpha=0.3)(up6)
  merge6 = merge([drop4,up6], mode = 'concat', concat_axis = 3)
  conv6 = Conv2D(512, 3, padding = 'same', kernel_initializer = 'he_normal')(merge6)
  conv6 = LeakyReLU(alpha=0.3)(conv6)
  conv6 = Conv2D(512, 3, padding = 'same', kernel_initializer = 'he_normal')(conv6)
  conv6 = LeakyReLU(alpha=0.3)(conv6)

  up7 = Conv2D(256, 2, padding = 'same', kernel_initializer = 'he_normal')(UpSampling2D(size = (2,2))(conv6))
  up7 = LeakyReLU(alpha=0.3)(up7)
  merge7 = merge([conv3,up7], mode = 'concat', concat_axis = 3)
  conv7 = Conv2D(256, 3, padding = 'same', kernel_initializer = 'he_normal')(merge7)
  conv7 = LeakyReLU(alpha=0.3)(conv7)
  conv7 = Conv2D(256, 3, padding = 'same', kernel_initializer = 'he_normal')(conv7)
  conv7 = LeakyReLU(alpha=0.3)(conv7)

  up8 = Conv2D(128, 2,padding = 'same', kernel_initializer = 'he_normal')(UpSampling2D(size = (2,2))(conv7))
  up8 = LeakyReLU(alpha=0.3)(up8)
  merge8 = merge([conv2,up8], mode = 'concat', concat_axis = 3)
  conv8 = Conv2D(128, 3, padding = 'same', kernel_initializer = 'he_normal')(merge8)
  conv8 = LeakyReLU(alpha=0.3)(conv8)
  conv8 = Conv2D(128, 3, padding = 'same', kernel_initializer = 'he_normal')(conv8)
  conv8 = LeakyReLU(alpha=0.3)(conv8)

  up9 = Conv2D(64, 2, padding = 'same', kernel_initializer = 'he_normal')(UpSampling2D(size = (2,2))(conv8))
  up9 = LeakyReLU(alpha=0.3)(up9)
  merge9 = merge([conv1,up9], mode = 'concat', concat_axis = 3)
  conv9 = Conv2D(64, 3, padding = 'same', kernel_initializer = 'he_normal')(merge9)
  conv9 = LeakyReLU(alpha=0.3)(conv9)
  conv9 = Conv2D(64, 3, padding = 'same', kernel_initializer = 'he_normal')(conv9)
  conv9 = LeakyReLU(alpha=0.3)(conv9)
  conv9 = Conv2D(2, 3, padding = 'same', kernel_initializer = 'he_normal')(conv9)
  conv9 = LeakyReLU(alpha=0.3)(conv9)
  conv10 = Conv2D(1, 1, activation = 'sigmoid')(conv9)
  #   morpho = Lambda(lambda x: grey_dilation(grey_erosion(x,size=8),6))(conv10)

  model = Model(input = inputs, output = conv10)

  model.compile(optimizer = Adam(lr = 1e-4), loss = 'binary_crossentropy') #, metrics = [iou])
  #model.compile(optimizer = 'rmsprop', loss = 'binary_crossentropy', metrics = [iou])

  return model

def metric():
    """
    Definición de la métrica IoU (Intersection over Union)
    """
    pass
