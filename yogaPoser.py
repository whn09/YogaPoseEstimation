
from __future__ import division
import argparse, time, logging, os, math, tqdm, cv2
import numpy as np
import mxnet as mx
from mxnet import gluon, nd, image
from mxnet.gluon.data.vision import transforms
import matplotlib.pyplot as plt
import gluoncv as gcv
from gluoncv import data
from gluoncv.data import mscoco
from gluoncv.model_zoo import get_model
from gluoncv.data.transforms.pose import detector_to_simple_pose, heatmap_to_coord
from yoga.helpers.visualize_yoga import cv_plot_keypoints
import cv2
import time
import argparse
import imutils
from imutils.video import VideoStream
import os
import pandas as pd


os.environ['MXNET_CUDNN_AUTOTUNE_DEFAULT'] = '0'

# ctx = mx.cpu()
ctx = mx.gpu(0)
# detector_name = 'yolo3_mobilenet1.0_coco'
# detector_name = "ssd_512_mobilenet1.0_coco"       # network for detecting humans
detector_name = "ssd_512_resnet50_v1_coco"       # network for detecting humans

detector = get_model(detector_name, pretrained=True, ctx=ctx)
detector.reset_class(classes=['person'], reuse_weights={'person':'person'})  # only bother reporting class labeled "humans"
detector.hybridize()

# estimator = get_model('simple_pose_resnet18_v1b', pretrained='ccd24037', ctx=ctx)  # model used for pose estimation
estimator = get_model('simple_pose_resnet152_v1d', pretrained=True, ctx=ctx)  # model used for pose estimation
estimator.hybridize()

ap = argparse.ArgumentParser()
ap.add_argument('-i', '--image', type = str, required = False, help ='image path')
ap.add_argument('-v', '--vid', type = str, required = False, help ='video path')
ap.add_argument('-o', '--outfile', default = 'output.avi', help = 'outfile path')
args = vars(ap.parse_args())

using_vid_file = False

if args['vid'] is not None:         # If getting frames from video
    using_vid_file = True
    print('[INFO] using video file...')
    vid_path = os.path.join(os.getcwd(), args['vid'])
    print('[INFO] vid_path:', vid_path)
    vs = cv2.VideoCapture(vid_path)
    vid_writer = cv2.VideoWriter(args['outfile'],cv2.VideoWriter_fourcc(*'MJPG'), 10, (910, 512), True)  # For outfile writing  ( 500, 280)
    # vid_writer = cv2.VideoWriter(args['outfile'],cv2.VideoWriter_fourcc(*'MJPG'), 10, (683, 512), True)  # For outfile writing  ( 500, 280)
elif args['image'] is not None:
    print('[INFO] using image file...')
else:                              # If getting frames from webcam (default)
    print('[INFO] using camera...')
    vs = VideoStream(src=0).start()
    time.sleep(1.0)

#frame = vs.read()
#if using_vid_file:
#    frame = frame[1]
#(H, W) = frame.shape[:2]

def main():
    start = time.time()
    count = 0
    pose = None
    skip_frame = False     # to increase frame rate, I only process every other frame.

    #with open('data.txt', 'a') as outfile:
    
    while True:    # While there is video frames to process...

        if args['image'] is not None:
            frame = cv2.imread(args['image'])
        else:
            frame = vs.read()
                
        if using_vid_file:
            exists, frame = (frame) #with vid file, frame is a tuple. First value is boolean second is array of pixels
            if not exists: 
                break          #exit when there are no incoming frames
        # try:
        #     frame = np.fliplr(frame)   # I want to display the mirror image of input
        # except ValueError:
        #     print('[ERROR] video file not found, make sure to include path and extension i.e. \'./vid.mp4\'')
        #     break
        count += 1
        # frame = imutils.resize(frame, width=280)  
        frame = mx.nd.array(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).astype('uint8')
        img = None
        if not skip_frame:
            x, frame = gcv.data.transforms.presets.ssd.transform_test(frame, short = 512)  # , max_size = 280
            x = x.as_in_context(ctx)

            class_IDs, scores, bounding_boxs = detector(x)

            pose_input, upscale_bbox = detector_to_simple_pose(frame, class_IDs, scores, bounding_boxs, ctx=ctx)  # ,output_shape=(128, 96)
            if len(upscale_bbox) > 0:
                predicted_heatmap = estimator(pose_input)
                pred_coords, confidence = heatmap_to_coord(predicted_heatmap, upscale_bbox)
                img, pose = cv_plot_keypoints(frame, pred_coords, confidence, class_IDs, bounding_boxs, scores,
                                        box_thresh=0.5, keypoint_thresh=0.15)

                #The following lines were for saving vid info to a file
                #pose = args['vid'].split('/')
                #pose = pose[2][:-4]
                #outfile.write(pose + ', ')
                #for angle in angles:
                #    outfile.write(str(angle) + ', ')
                #outfile.write('\n')
                

                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                # print(img.shape)
            skip_frame = True

        else:
            skip_frame = False
        if img is None:
            continue
        
        # img = imutils.resize(img, height = 280, width = 500)    # blowup image for displaying
        
        if pose:
            cv2.putText(img, '{}'.format(pose), (20,20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        else:
            cv2.putText(img, 'No Pose Detected', (20,20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        if using_vid_file:
            vid_writer.write(img)
        # cv2.imshow('Webcam', img)
        # key = cv2.waitKey(1) & 0xFF

#         if key == ord("q"):
#             break
        if args['image'] is not None:
            cv2.imwrite('result.jpg', img)
            break

    # cv2.destroyAllWindows()
    if args['image'] is None and not using_vid_file:
        vs.stop()
    if using_vid_file:
        vid_writer.release()
    stop = time.time()
    #outfile.close()
    print("fps: {}".format(count/(stop-start)))
    

if __name__ == '__main__': 
    
    main()
   

