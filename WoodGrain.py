#!/usr/bin/env python
#Name: Wood Grain
#Info: Vary the print temperature troughout the print to create wood rings with some printing material such as the LayWoo. The higher the temperature, the darker the print.
#Depend: GCode
#Type: postprocess
#Param: minTemp(float:180) Mininmum print temperature (degree C)
#Param: maxTemp(float:230) Maximun print temperature (degree C)
#Param: grainSize(float:3.0) Average "wood grain" size (mm)
#Param: firstTemp(float:0) Starting temperature (degree C, zero to disable)
#Param: spikinessPower(float:1.0) Relative thickness of light bands (power, >1 to make dark bands sparser)
#Param: maxUpward(float:0) Instant temperature increase limit, as required by some firmwares (C)
#Param: zOffset(float:0) Vertical shift of the variations, as shown at the end of the gcode file (mm)
#
# Original Author: Jeremie Francois (jeremie.francois@gmail.com)
# License: GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
# Heavily Modified by: Zhu Da Hai. Sept 2, 2016 (appologies to Jeremie)
# Compatible with: Cura 2.6.2 - Sort of
# 2017-07-23: (DaHai) Fixed issue with Relative Move Z-hop in End Gcode of some profiles messing up lastPatchZ  
#
# Bug: Does not always generate M104 Wood Grain changes for the last few layers, no does it always give a layer graph at the end
#
from ..Script import Script
import re
import random
import math
import time
import datetime

eol = "\n"

import inspect
import sys
import getopt

class WoodGrain(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return {
            "name":"Wood Grain",
            "key": "WoodGrain",
            "metadata":{},
            "version": 2,
            "settings":
            {
                "a_minTemp": 
                {
                    "label": "Min Temp",
                    "description": "Mininmum print temperature (degree C)",
                    "unit": "c",
                    "type": "float",
                    "default_value": 180
                },
                "b_maxTemp": 
                {
                    "label": "Max Temp",
                    "description": "Maximun print temperature (degree C)",
                    "unit": "c",
                    "type": "float",
                    "default_value": 230
                },
                "c_firstTemp": 
                {
                    "label": "First Temp",
                    "description": "Starting temperature (degree C, zero to disable)",
                    "unit": "c",
                    "type": "float",
                    "default_value": 0
                },
                "d_grainSize": 
                {
                    "label": "Grain Size",
                    "description": "Average 'wood grain' size (mm)",
                    "unit": "mm",
                    "type": "float",
                    "default_value": 3.0
                },
                "e_maxUpward": 
                {
                    "label": "Max Upward",
                    "description": "Instant temperature increase limit, as required by some firmwares (C)",
                    "unit": "c",
                    "type": "float",
                    "default_value": 0
                },
                "f_zOffset": 
                {
                    "label": "Z-Offset",
                    "description": "Vertical shift of the variations, as shown at the end of the gcode file (mm)",
                    "unit": "mm",
                    "type": "float",
                    "default_value": 1.0
                },
                "g_randomSeed": 
                {
                    "label": "Random Seed",
                    "description": "Seed for Random Number Generator (0 = no seed - randomize)",
                    "unit": "",
                    "type": "int",
                    "default_value": 0
                },
                "h_spikinessPower": 
                {
                    "label": "Spikiness Power",
                    "description": "Relative thickness of light bands (power, >1 to make dark bands sparser)",
                    "unit": "",
                    "type": "float",
                    "default_value": 1.0
                }
            }
        }
    
    def getValue(self, line, key, default = None):
        if not key in line or (';' in line and line.find(key) > line.find(';')):
            return default
        sub_part = line[line.find(key) + len(key):]
        m = re.search('^[-+]?[0-9]+\.?[0-9]*', sub_part)
        if m is None:
            return default
        try:
            return float(m.group(0))
        except:
            return default

    def getZ(self, line, default = None):
        # new 20130727: now support G0 in addition to G1
        if self.getValue(line, 'G') == 0 or self.getValue(line, 'G') == 1:
            return self.getValue(line, 'Z', default)
        else:
            return default

    try:
        xrange
    except NameError:
        xrange = range

    def perlinToNormalizedWood(self, z, zOffset, grainSize, spikinessPower, perlin):
        banding = 3
        octaves = 2
        persistence = 0.7
        noise = banding * perlin.fractal(octaves, persistence, 0,0, (z+zOffset)/(grainSize*2));
        noise = (noise - math.floor(noise)) # normalized to [0,1]
        noise= math.pow(noise, spikinessPower)
        return noise
    
    def noiseToTemp(self, noise, maxTemp, minTemp):
        return minTemp + noise * (maxTemp - minTemp)

    class Perlin:
        # Perlin noise: http://mrl.nyu.edu/~perlin/noise/
    
        def __init__(self, tiledim=256):
            self.tiledim= tiledim
            self.perm = [None]*2*tiledim
    
            permutation = []
            # xrange changed to range for Python3
            for value in range(tiledim):
                permutation.append(value)
            random.shuffle(permutation)
    
            # xrange changed to range for Python3
            for i in range(tiledim):
                self.perm[i] = permutation[i]
                self.perm[tiledim+i] = self.perm[i]
    
        def fade(self, t):
            return t * t * t * (t * (t * 6 - 15) + 10)
    
        def lerp(self, t, a, b):
            return a + t * (b - a)
    
        def grad(self, hash, x, y, z):
            #CONVERT LO 4 BITS OF HASH CODE INTO 12 GRADIENT DIRECTIONS.
            h = hash & 15
            if h < 8: u = x
            else:     u = y
            if h < 4: v = y
            else:
                if h == 12 or h == 14: v = x
                else:                  v = z
            if h&1 == 0: first = u
            else:        first = -u
            if h&2 == 0: second = v
            else:        second = -v
            return first + second
    
        def noise(self, x,y,z):
            #FIND UNIT CUBE THAT CONTAINS POINT.
            X = int(x)&(self.tiledim-1)
            Y = int(y)&(self.tiledim-1)
            Z = int(z)&(self.tiledim-1)
            #FIND RELATIVE X,Y,Z OF POINT IN CUBE.
            x -= int(x)
            y -= int(y)
            z -= int(z)
            #COMPUTE FADE CURVES FOR EACH OF X,Y,Z.
            u = self.fade(x)
            v = self.fade(y)
            w = self.fade(z)
            #HASH COORDINATES OF THE 8 CUBE CORNERS
            A = self.perm[X  ]+Y; AA = self.perm[A]+Z; AB = self.perm[A+1]+Z
            B = self.perm[X+1]+Y; BA = self.perm[B]+Z; BB = self.perm[B+1]+Z
            #AND ADD BLENDED RESULTS FROM 8 CORNERS OF CUBE
            return self.lerp(w,self.lerp(v,
                    self.lerp(u,self.grad(self.perm[AA  ],x  ,y  ,z  ), self.grad(self.perm[BA  ],x-1,y  ,z  )),
                    self.lerp(u,self.grad(self.perm[AB  ],x  ,y-1,z  ), self.grad(self.perm[BB  ],x-1,y-1,z  ))),
                self.lerp(v,
                    self.lerp(u,self.grad(self.perm[AA+1],x  ,y  ,z-1), self.grad(self.perm[BA+1],x-1,y  ,z-1)),
                    self.lerp(u,self.grad(self.perm[AB+1],x  ,y-1,z-1), self.grad(self.perm[BB+1],x-1,y-1,z-1))))
    
        def fractal(self, octaves, persistence, x,y,z, frequency=1):
            value = 0.0
            amplitude = 1.0
            totalAmplitude= 0.0
            # xrange changed to range for Python3
            for octave in range(octaves):
                n= self.noise(x*frequency,y*frequency,z*frequency)
                value += amplitude * n
                totalAmplitude += amplitude
                amplitude *= persistence
                frequency *= 2
            return value / totalAmplitude


    def execute(self, data: list):

        minTemp = float(self.getSettingValueByKey("a_minTemp"))
        maxTemp = float(self.getSettingValueByKey("b_maxTemp"))
        firstTemp = float(self.getSettingValueByKey("c_firstTemp"))
        grainSize = float(self.getSettingValueByKey("d_grainSize"))
        maxUpward = float(self.getSettingValueByKey("e_maxUpward"))
        zOffset = float(self.getSettingValueByKey("f_zOffset"))
        randomSeed = int(self.getSettingValueByKey("g_randomSeed"))
        spikinessPower = float(self.getSettingValueByKey("h_spikinessPower"))
        myStr = ""

        if randomSeed != 0:
            random.seed( randomSeed )

        # new 20130727: limit the number of changes for helicoidal/Joris slicing method
        minimumChangeZ=0.1
        
        perlin = WoodGrain.Perlin()
        
        # Generate normalized noises, and then temperatures (will be indexed by Z value)
        noises = {}
    
        # first value is hard encoded since some slicers do not write a Z0 at the first layer!
        # TODO: keep only Z changes that are followed by real extrusion (ie. discard non-printing head movements!)
        noises[0] = self.perlinToNormalizedWood(0, zOffset, grainSize, spikinessPower, perlin)
        pendingNoise = None
        formerZ = -1
        thisZ = -1
        absolute = False
        firstLayer = False

        for index, layer in enumerate(data):
            #index = data.index(layer)
            lines = layer.split("\n")
            for line in lines:
                if "G90" in line :
                    absolute = True
                if "G91" in line :
                    absolute = False
                if absolute :
                    thisZ = self.getZ(line, formerZ)
                    if thisZ > 2 + formerZ:
                        formerZ = thisZ
                        #noises = {} # some damn slicers include a big negative Z shift at the beginning, which impacts the min/max range
                    elif abs ( thisZ - formerZ ) > minimumChangeZ:
                        formerZ = thisZ
                        noises[thisZ] = self.perlinToNormalizedWood(thisZ, zOffset, grainSize, spikinessPower, perlin);
                        # layer = ";thisZ|noises = "+str(thisZ)+"|"+str(noises[thisZ])+eol+layer
            #data[index] = layer
        # return data
    
        lastPatchZ = thisZ # record when to stop patching M104, to leave the last one switch the temperature off
        # lastPatchZ = 10.1
        
        # normalize built noises
        noisesMax = noises[max(noises, key = noises.get )]
        noisesMin = noises[min(noises, key = noises.get )]
        for z,v in noises.items():
            noises[z]= (noises[z]-noisesMin)/(noisesMax-noisesMin)
        

        #
        # new 20130727: header and first (blocking) temperature change
        #
        warmingTempCommands="M230 S0" + eol # enable wait for temp on the first change
        if firstTemp == 0:
            warmingTempCommands+= ("M104 S%i" + eol) % self.noiseToTemp(0, maxTemp, minTemp)
        else:
            warmingTempCommands+= ("M104 S%i" + eol) % firstTemp
        # The two following commands depends on the firmware:
        warmingTempCommands+= "M230 S1" + eol # now disable wait for temp on the first change
        warmingTempCommands+= "M116" + eol # wait for the temperature to reach the setting (M109 is obsolete)

        # Prepare a transposed temperature graph for the end of the file
        graphStr=";WoodGraph: Wood temperature graph (from "+str(minTemp)+"C to "+str(maxTemp)+"C, grain size "+str(grainSize)+"mm, z-offset "+str(zOffset)+")"
        if maxUpward:
            graphStr+=", temperature increases capped at "+str(maxUpward)
        graphStr+=":"
        graphStr+=eol

        thisZ = -1
        formerZ = -1
        warned = 0
        header = 1
        savelayer = 0
        
        postponedTempDelta=0 # only when maxUpward is used
        postponedTempLast=None # only when maxUpward is used
        skiplines=0

        # Now Modify the gCode
        for index, layer in enumerate(data):
            if header == 1:
                layer = warmingTempCommands + layer
                data[index] = layer #Override the data of this layer with the modified data
                header = 0
            lines = layer.split("\n")
            for line in lines:
                if "; set extruder " in line.lower(): # special fix for BFB
                    layer = layer.replace(line,line + "\n" + warmingTempCommands)
                    warmingTempCommands=""
                    savelayer = 1
                elif skiplines > 0:
                    skiplines= skiplines-1;
                elif ";woodified" in line.lower():
                    skiplines=4 # skip 4 more lines after our comment
                elif not ";woodgraph" in line.lower(): # forget optional former temp graph lines in the file
                    if thisZ == lastPatchZ:
                        line = line # dummy
                    elif not "m104" in line.lower(): # forget any previous temp in the file
                        thisZ = self.getZ(line, formerZ)
                        if thisZ != formerZ and thisZ in noises:
                            if firstTemp != 0 and thisZ<=0.5: # if specifed, keep the first temp for the first 0.5mm
                                temp= firstTemp
                            else:
                                temp= self.noiseToTemp(noises[thisZ], maxTemp, minTemp)
                                # possibly cap temperature change upward
                                temp += postponedTempDelta;
                                #print("ppdelta=%f\n" % postponedTempDelta)
                                postponedTempDelta = 0
                                if postponedTempLast!= None and maxUpward > 0 and temp > postponedTempLast + maxUpward:
                                    postponedTempDelta = temp - (postponedTempLast + maxUpward)
                                    temp= postponedTempLast + maxUpward
                                if temp > maxTemp:
                                    postponedTempDelta= 0
                                    temp= maxTemp
                                postponedTempLast = temp
                                layer = layer.replace(line,line + "\n" + ("M104 S%i ; Wood Grain" + eol) % temp)
                                savelayer = 1
                            formerZ = thisZ
                            
                            # Build the corresponding graph line
                            #t = int(19 * noises[thisZ])
                            t= int(19 * (temp-minTemp)/(maxTemp-minTemp))
                            myStr = ";WoodGraph: Z %03f " % thisZ
                            myStr += "@%3iC | " % temp
                            # xrange changed to range for Python3
                            for i in range(0,t):
                                myStr += "#"
                            # xrange changed to range for Python3
                            for i in range(t+1,20):
                                myStr += "."
                            graphStr += myStr + eol

            if savelayer == 1:
                data[index] = layer
                savelayer = 0
                
        layer = layer + graphStr + eol
        data[index] = layer
        return data    
