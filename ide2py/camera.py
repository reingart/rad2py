#!/usr/bin/env python
# coding:utf-8

"Camera sensor to track user activity automatically using OpenCV face detection"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2014 Mariano Reingart"
__license__ = "GPL 3.0"


import wx
import cv2
import time


class Camera(wx.Panel):
    "Widget to capture and display images (with faces detection)"
    
    def __init__(self, parent, rate=5, width=320, height=240,
                 classpath="haarcascade_frontalface_default.xml"):
        wx.Panel.__init__(self, parent, -1, wx.DefaultPosition, 
                                wx.Size(width, height))
        self.parent = parent

        # set up OpenCV features:
        self.capture = cv2.VideoCapture(0)
        self.capture.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, height)
        self.classifier = cv2.CascadeClassifier(classpath)

        # create an initial bitmap with a compatible OpenCV image bit depth
        self.bmp = wx.EmptyBitmap(width, height, 24)

        # Initialize sampling capture rate (default: one shot per second)
        self.timer = wx.Timer(self)
        self.timer.Start(500.)
        self.count = 0
        self.rate = rate
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_TIMER, self.OnTimer)

    def OnTimer(self, evt):
        "Capture a single frame image and detect faces on it"
        t0 = time.time()
        # Capture a image frame twice a second to flush buffers:
        self.capture.grab()
        ##print "grabbing", self.count
        self.count += 1
        if self.count % (self.rate * 2):
            return
        # Process the image frame (default sampling rate is 5 seconds)
        t1 = time.time()
        ret, img = self.capture.retrieve()
        if ret:
            # Detect faces using OpenCV (it needs the gray scale conversion):
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self.classifier.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(85, 85),
                flags=cv2.cv.CV_HAAR_SCALE_IMAGE
            )
            t2 = time.time()
            if False: print "faces", faces, t1-t0, t2-t1
            # Draw detected faces over the color original image:
            for (x, y, w, h) in faces:
                cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 4)
            self.bmp.CopyFromBuffer(img)
            self.Refresh()
            # Notify PSP parent component about the detected change (if any):
            if not len(faces):
                self.parent.PSPInterrupt("cam")
            else:
                self.parent.PSPResume("cam")

    def OnPaint(self, evt):
        "Draw the captured image to the screen"
        dc = wx.BufferedPaintDC(self)
        width, height = self.GetSize()
        # resize the image up to the panel dimensions, and draw it:
        image = wx.ImageFromBitmap(self.bmp)
        image = image.Scale(width, height, wx.IMAGE_QUALITY_NORMAL)
        dc.DrawBitmap(wx.BitmapFromImage(image), 0, 0)


if __name__ == "__main__":
    # Test application:
    app = wx.App()
    frame = wx.Frame(None)
    cam = Camera(frame)
    frame.SetSize(cam.GetSize())        
    frame.Show()
    app.MainLoop()

