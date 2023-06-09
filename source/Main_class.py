import os
import time
import cv2
import numpy as np
from helper import preprocess
import datetime
import random

from segment import wordSegmentation
from Preprocessing import imformation_crop, removeline, removecircle
from digit_model import build_digit_model
from word_model import build_word_model
from create_metrics_OCR import cer, wer, _levenshtein_distance
from Excel import class_list,lexicon_search,writing_to_excel


import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


############# Initial Config ###################

class_list_dir = 'data\Class_list.xlsx'
name_list, MSSV_list, name_MSSV_list, Diem_list = class_list(class_list_dir)

with open('data\scoreList.txt', "r", encoding="utf-8") as f:
    reader = f.read()
scoreDict = sorted(reader.split(' '))

def num_to_label(num,alphabets):
    ret = ""
    for ch in num:
        if ch == -1:  # CTC Blank
            break
        else:
            ret+=alphabets[ch]
    return ret

image_size = 0
acc_index = 0
acc_score = 0
uncorrect_index = []
uncorrect_score = []
############## RESTORE MODEL ##########
#Name model
with open('data/charList.txt', 'r', encoding='utf-8') as f:
    alphabets_word = f.read()

max_str_len_word = 15
word_model, word_model_CTC = build_word_model(alphabets = alphabets_word, max_str_len = max_str_len_word)
#word_model.summary()
word_model_dir = r'model\word_model\word_model_last_6.h5'

word_model.load_weights(word_model_dir)


## MSSV model
alphabets_digit = '0123456789'
max_str_len_digit = 10
digit_model, digit_model_CTC = build_digit_model(alphabets = alphabets_digit, max_str_len = max_str_len_digit)
#digit_model.summary()
digit_model_dir = r'model\digit_model\digit_model_last_2022-07-05.h5'
digit_model.load_weights(digit_model_dir)

for filename in os.listdir("data\Class_list_constrained"):
    image_size += 1
    print ('\n............................................\n')
    print ('FILENAME',filename)

    real_index = int(filename[7:-4])

    filepath  = os.path.join("data\Class_list_constrained"+ '/', filename)
    
    start = time.time()
    giaythi  = cv2.imread(filepath, cv2.IMREAD_COLOR)
    (MSSV_crop, name_crop, diem_crop) = imformation_crop(giaythi)

    print ('\nimg shape',giaythi.shape)
    print ('MSSV_crop shape',MSSV_crop.shape)
    print ('diem_crop shape',diem_crop.shape)
    print ('name_crop shape',name_crop.shape,'\n')

    ############### NAME_RECOGNITION ######################
    name_crop_copy = name_crop.copy()
    name_crop_copy = removeline(name_crop_copy)

    #if not os.path.exists('doc/removelineresult'):
    #    os.mkdir('doc/removelineresult')
    #imwritepath = os.path.join('doc/removelineresult/namecrop_' + filename)
    #cv2.imwrite(str(imwritepath),name_crop_copy)
    
    result = wordSegmentation(name_crop_copy, kernelSize=21, sigma=11, theta=4, minArea=500)
    name_recognized = str()
    draw = []
    i = 0
    for line in result:
        if len(line):
            for (_, w) in enumerate(line):
                (wordBox, wordImg) = w
                ##################
                print ('wordImg.shape',wordImg.shape)
                cv2.imshow('wordImg '+ str(i),wordImg)

                wordImg = preprocess(wordImg, imgSize = (128, 32))
                wordImg = np.array(wordImg).reshape(-1, 128, 32, 1)
                pred_names = word_model.predict(wordImg)

                decoded_names = tf.keras.backend.get_value(tf.keras.backend.ctc_decode(pred_names, input_length=np.ones(pred_names.shape[0])*pred_names.shape[1], 
                                        greedy=False,
                                        beam_width=50,
                                        top_paths=1)[0][0])
                name_recognized += num_to_label(decoded_names[0], alphabets = alphabets_word) + ' ' 
                #Its just an approx name
                draw.append(wordBox)
                i = i+1
    

    ############### MSSV_RECOGNITION #######################

    #cv2.imshow('MSSV_crop',MSSV_crop)

    MSSV_crop_copy = MSSV_crop.copy()
    MSSV_crop_copy = removeline(MSSV_crop_copy)
    
    #cv2.imshow('MSSV_crop_copy',MSSV_crop_copy)

    MSSV_crop_copy = preprocess(MSSV_crop_copy,(128,32))

    pred_MSSV = digit_model.predict(np.array(MSSV_crop_copy).reshape(-1, 128, 32, 1))
    decoded_MSSV = tf.keras.backend.get_value(tf.keras.backend.ctc_decode(pred_MSSV, input_length=np.ones(pred_MSSV.shape[0])*pred_MSSV.shape[1], 
                                        greedy=False,
                                        beam_width=5,
                                        top_paths=1)[0][0])

    MSSV_recognized = num_to_label(decoded_MSSV[0], alphabets = alphabets_digit) 
    
    print('\nNAME_approx: ' + name_recognized)
    print('MSSV_approx: ' + MSSV_recognized)

    name_MSSV_recognized = name_recognized.strip() + ' ' + MSSV_recognized.strip()        
    name_MSSV_index, name_MSSV_recognized,_ = lexicon_search (name_MSSV_recognized, name_MSSV_list)
    print ('\nname_MSSV_recognized:',name_MSSV_recognized)

    if real_index == name_MSSV_index + 2:
        acc_index += 1    
        print ('Name & MSSV Accuracy:%.2f%%' %(acc_index*100/image_size))
    else:
        uncorrect_index.append(real_index)
    ############### Diem_RECOGNITION #######################

    diem_crop_copy = diem_crop.copy()

    diem_crop_copy = removecircle(diem_crop_copy)
    print ('diem_crop_copy thresh hold',diem_crop_copy.shape)
    #cv2.imshow('removecircle',diem_crop_copy)

    diem_recognized =str()
    diem_crop_copy = preprocess(diem_crop_copy, imgSize = (128, 32))
    diem_crop_copy = np.array(diem_crop_copy).reshape(-1, 128, 32, 1)

    pred_diem = digit_model.predict(diem_crop_copy)

    decoded_diem = tf.keras.backend.get_value(tf.keras.backend.ctc_decode(pred_diem, input_length=np.ones(pred_diem.shape[0])*pred_diem.shape[1], 
                                            greedy=False,
                                            beam_width=5,
                                            top_paths=1)[0][0])

    diem_recognized = num_to_label(decoded_diem[0], alphabets = alphabets_digit) 

    print ('\ndiem approx: ', diem_recognized)
    _, diem_recognized,_ = lexicon_search (diem_recognized, scoreDict)

    if diem_recognized != '10':
        diem_recognized = diem_recognized[:1]+ '.' + diem_recognized[1:]
    diem_recognized = float(diem_recognized)    
    print('diem_recognized: '+ str(diem_recognized))

    print ('Diem_list real_index: ',Diem_list[real_index-2])
    if diem_recognized == Diem_list[real_index-2]:
        acc_score += 1
        print ('Score Accuracy:%.2f%%' %(acc_score*100/image_size))
    else:
        uncorrect_score.append(real_index)

    writing_to_excel (class_list_dir, name_MSSV_index + 2,diem_recognized)
    end = time.time()
    # show timing information on text prediction
    print("[INFO] main took {:.6f} seconds".format(end - start))

print ('\nThe total images: {}'.format(image_size))
print ('The number of uncorrect score: {}. The number of uncorrect index: {}.'.format(len(uncorrect_score),len(uncorrect_index)))
print ('The uncorrect index are:', uncorrect_index)
print ('The uncorrect score are:', uncorrect_score)
print ('\nName & MSSV Accuracy:%.2f%%' %(acc_index*100/image_size))
print ('Score Accuracy:%.2f%%' %(acc_score*100/image_size))

with open('result_100_103.txt', 'a', encoding='utf-8') as f:
    
    f.writelines('\n--------------------------\nResult on Class_{}'.format(image_size))
    f.writelines ('\n\nword_model_dir: {}'.format(word_model_dir))
    f.writelines ('\ndigit_model_dir: {}'.format(digit_model_dir))

    f.writelines ('\n\nThe number of correct recognization: {}. The total images: {}'.format(acc_index, image_size))
    f.writelines ('\nThe uncorrect index are:{}'.format(uncorrect_index))
    f.writelines ('\nThe uncorrect score are:{}'.format(uncorrect_score))
    f.writelines ('\n\nName & MSSV Accuracy:{:.2f}%'.format((acc_index*100/image_size)))
    f.writelines ('\nScore Accuracy:{:.2f}%'.format((acc_score*100/image_size)))

cv2.waitKey(0)
