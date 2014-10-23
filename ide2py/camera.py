#!/usr/bin/env python
# coding:utf-8

"Camera sensor to track user activity automatically using OpenCV face detection"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2014 Mariano Reingart"
__license__ = "GPL 3.0"


import wx
import cv, cv2


class Camera(wx.Panel):
    "Widget to capture and display images (with faces detection)"
    
    def __init__(self, parent, rate=1, width=320, height=240,
                 classpath="haarcascade_frontalface_default.xml"):
        wx.Panel.__init__(self, parent, -1, wx.DefaultPosition, 
                                wx.Size(width, height))

        # set up OpenCV features:
        self.capture = cv2.VideoCapture(0)
        self.capture.set(cv.CV_CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv.CV_CAP_PROP_FRAME_HEIGHT, height)
        self.classifier = cv2.CascadeClassifier(classpath)

        self.bmp = wx.EmptyBitmap(width, height)

        # Initialize sampling capture rate (default: one shot per second)
        self.timer = wx.Timer(self)
        self.timer.Start(rate * 1000.)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_TIMER, self.OnTimer)        

    def OnTimer(self, evt):
        "Capture a single frame image and detect faces on it"
        ret, img = self.capture.read()
        if ret:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self.classifier.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30),
                flags=cv2.cv.CV_HAAR_SCALE_IMAGE
            )
            print "faces", faces
            for (x, y, w, h) in faces:
                cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
            self.bmp.CopyFromBuffer(img)
            self.Refresh()

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

