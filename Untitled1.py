import sys, os, web, subprocess, urllib, json, glob, shutil, re
from collections import OrderedDict
from shutil import copyfile

MARXAN_FOLDER = "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/"
MARXAN_EXECUTABLE = MARXAN_FOLDER + "MarOpt_v243_Linux64"
MARXAN_OUTPUT_FOLDER = MARXAN_FOLDER + "output" + os.sep 
MARXAN_INPUT_PARAMETER_FILENAME = MARXAN_FOLDER + "input.dat"
MARXAN_INPUT_FOLDER = MARXAN_FOLDER + "input" + os.sep

def readFile(filename):
    f = open(filename)
    s = f.read()
    f.close()
    return s
    
def writeFile(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()
    
def getKeyValue(text, parameterName):
    p1 = text.index(parameterName)
    value = text[p1 + len(parameterName) + 1:text.index("\r",p1)]
    return parameterName[1:], value

#gets the position of the end of the line which may be different in windows/unix generated files
def getEndOfLine(text):
    try:
        p = text.index("\r\n") 
    except (ValueError):
        p = text.index("\n") 
    return p

#gets a single input parameter, i.e. the actual value and not the parameter name
def getInputParameter(filename, parameter):
    #get the file contents
    s = readFile(filename)
    p1 = s.index(parameter) #get the first position of the parameter
    if p1>-1:
        p2 = s[p1:].index(" ") #get the position of the space
        if p2 > 0:
            p3 = getEndOfLine(s[p1:]) #get the position of the end of line
            if p3 > 0:
                return s[p1 + p2 + 1:p1 + p3]
        

#updates the parameters in the *.dat file with the new parameters passed as a dict
def updateParameters(data_file, newParams):
    if newParams:
        #get the existing parameters 
        s = readFile(data_file)
        print s
        #update any that are passed in as query params
        for k, v in newParams.iteritems():
            try:
                p1 = s.index(k) #get the first position of the parameter
                if p1>-1:
                    p2 = getEndOfLine(s[p1:]) #get the position of the end of line
                    s = s[:p1] + k + " " + v + s[(p1 + p2):]
                #write these parameters back to the *.dat file
                writeFile(data_file, s)
            except ValueError:
                continue
    return 

user_folder = MARXAN_FOLDER + "andrew/user.dat"
f = MARXAN_FOLDER + "andrew/Sample scenario/input.dat"

print updateParameters(f, {"MAPID":"wibble"})
