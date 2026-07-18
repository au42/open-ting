~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
    __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
   (______)(______)(______)(______)(______)(______)(______)(______)(______)                                                                                                                                                      
++-------------------------------------------------------------------------++
++-------------------------------------------------------------------------++
||                                                                         ||
||                                                                         ||
||                      TEENAGE ENGINEERING PRESENTS                       ||
||                                                                         ||
||                                                                         ||
||                                  =                 ==                   ||
||                         = =     =      =        =   =                   ||
||                =   ==        = =  =     =     =            =  =         ||
||              =                 +      = =           ==    =             ||
||                                                           =             ||
||                 +  ======= ==   ======    ======   FX     = ==          ||
||                =   ======= ==  ========  ========            ==         ||
||             =      ======= ==  ========  ========              =        ||
||          =         ======= ==  ========  ========           ==          ||
||       =               =    ==  ==    ==  ==               =             ||
||          ==           =    ==  ==    ==  ==  ====      =                ||
||                =      =    ==  ==    ==  === ====       = = =           ||
||              =        =    ==  ==    ==  ========       ===             ||
||              =        =    ==  ==    ==  ========      =                ||
||           =           =    ==  ==    ==   ======     =                  ||
||                                                       ==                ||
||         =   = = =                      =                =               ||
||                =        ==         =    =          =       -            ||
||                =    =        =      =     = =    =    =     =           ||
||                   =          =   =         =   =           = =          ||
||              =  =            =-            ===                          ||
||                                                                         ||
||                                                                         ||
++-------------------------------------------------------------------------++
++-------------------------------------------------------------------------++
   ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
    __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
   (______)(______)(______)(______)(______)(______)(______)(______)(______)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~                                                                                                                                                     
# TING
thank you for buying EP-2350 TING, a full instruction and warranty terms can be
found on teenage engineering's website https://teenage.engineering

## using TING
power it by inserting 2 x AAA batteries or attaching to a USB power source.
push the handle to start. you must also push the handle to enable the microphone.

on batteries:
  * 5 min after releasing the handle the unit goes into power save mode
  * 20 min after releasing the handle the unit turns off
  * if the battery voltage is too low an LED will blink
    and the unit will not turn on
  * remove the batteries if the unit is stored

on usb power:
  * the unit will stay powered until you pull the cable
  * the batteries are not used if there is usb power
  * the batteries are not charged

WARNING: loud sound levels leads to hearing loss. TING is designed to connect
to the RIDDIM or an audio mixer, not directly to headphones.

signal level out is 2 VRMS and this can be very loud connecting directly to
headphones, under the lid there is a round green turn to adjust the volume.

the orange button selects between clean voice and 4 effect presets
some of the effect parameters are modulated by the position of the handle,
some are effected by if you shake the unit.

    [ clean, echo, echo+spring, pixie, robot ]

the green button selects between 4 preset samples. if you want to
you can change these to your own samples.

    [ siren, alarm, gunshot, monkey boy ]

the white button plays the selected sample.

### pushing the handle

the position of the handle can change the amount of an effect.

### shaking the unit

shaking the unit temporarily modifies the sound of the effect,
how is preset dependent.

## upgrading the firmware

first you will need a firmware uf2 file. if there is a new firmware this can
be downloaded from teenage engineering's website.
remove the lower lid and  attach a usb-c cable to your computer,
hold in the handle and then double click the small button above the usb port.
a drive called TING BOOT should appear in your computer containing the files
INDEX.HTM and INFO_UF2.TXT, drag and drop the firmware file to this drive
and wait until transferred and the unit restarts. do not release the handle
until the the operation is finished.

## changing the samples

overriding a preset sample with your own sample is done by placing files called
1.wav, 2.wav, 3.wav and 4.wav on the TING DISK. only wav format is allowed and
the total file size is about 1 MB. the samples can be mono or stereo, 8/16/24-bit
or 32-bit floating point, with a frequency up to 96 kHz. the samples are not
available until the unit is restarted, push the button over the usb-c port
turn it off and push the handle to start again.

## config.json

a file called config.json overrides the presets and selects what samples to play.
json is a human-readable data exchange format that that TING can interpret.
please look at the example syntax and you will be able to write your own.
some effects like delay, reverb, harmony and ssb should only be used ones per
effect chain. parameters not initialized will have a default value. if your
config file is so extreme that the unit will not start, hold green + white
button when starting and then fix the file.

### example
~~~
{
  "name": "We count from zero",
  "samples": [
    { "pos": 1, "file": "samples/whistle1.wav","playmode": "oneshot" },
    { "pos": 0, "file": "live1/loop.wav","playmode": "startstop" },
    { "file": "horn.wav","playmode": "hold" },
    { "file": "live1/shottis.wav","playmode": "oneshot" }
  ],
  "presets": [
    {
      "pos": 0,
      "list": [
        { "effect": "HARMONY", "pitch": 2.0, "BUS": 2   },
        { "effect": "REVERB", "time": 0.1, "dry-level": 1.0 },
        { "effect": "DELAY","time": 0.5, "dry-level": 0.0, "echo": 0.5, "BUS": 1 },
        { "effect": "SAMPLE", "speed": 1.0 }
      ],
      "handle": { "row": 1, "param": "time","depth": 0.6 },
      "shake": { "row": 2, "param": "echo", "depth": 1.0 },
      "lfo": { "row": 3, "param": "echo", "depth": 1.0,
               "mpy": 1.0, "shape": "random", "phase": 0, "speed", 4.0 },
      "trigger": { "row": 3 }

    },
    {
      "pos": 2,
      "list": [
        { "effect": "HARMONY", "pitch": 2.0 },
        { "effect": "SAMPLE", "speed": 2.0 },
        { "effect": "REVERB", "time": 1.0, "spring": 0.5 },
        { "effect": "DELAY", "time": 0.1, "echo": 0.5 }
      ],
      "handle": { "row": 2, "param": "pitch", "depth": -0.2 },
      "trigger": { "row": 1 }

    }
  ]
}
~~~
### effects
    BALANCE:
        balance             [0.0, 1.0]

    DELAY:
        time                [0.0, 1.2]
        lowpass-cutoff      [0.0, 1.0]
        highpass-cutoff     [0.0, 1.0]
        wet-level           [0.0, 1.0]
        dry-level           [0.0, 1.0]
        echo                [0.0, 1.0]
        cross-feed          [0.0, 1.0]
        balance             [0.0, 1.0]

    DIST:
        amount              [0.0, 40.0]
        highpass-cutoff     [0.0, 1.0]
        lowpass-cutoff      [0.0, 1.0]
        mix                 [0.0, 1.0]

    HARMONY:
        dry-level           [0.0, 1.0]
        pitch               [0.50, 2.0]

    HIGHPASS:
        cutoff              [0.0, 1.0]

    LOWPASS:
        cutoff              [0.0, 1.0]

    SAMPLE:
        speed               [0.0, 4.0]
        pitch               [-24.0, 24.0]
        level               [0.0, 1.0]
        balance             [0.0, 1.0]

    REVERB:
        dry-level           [0.0, 1.0]
        wet-level           [0.0, 1.0]
        time                [0.0, 1.0]
        spring-mix          [0.0, 1.0]
        highpass-cutoff     [0.0, 1.0]

    RING:
        frequency           [0.0, 20000.0]
        mix                 [0.0, 1.0]

    SSB:
        frequency           [-20000.0, 20000.0]

### LFO shapes

    [ sine, square, sawtooth, random ]

## Licenses

copyright (c) 2025 teenage engineering, all rights reserved,
teenage engineering holds all rights to its registered trademarks.

### PICO SDK

Copyright (c) 2020 Raspberry Pi (Trading) Ltd.

  1. Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.

  2. Redistributions in binary form must reproduce the above copyright notice,
     this list of conditions and the following disclaimer in the documentation
     and/or other materials provided with the distribution.

  3. Neither the name of the copyright holder nor the names of its contributors
     may be used to endorse or promote products derived from this software
     without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

### MICROPYTHON

Copyright (c) 2013-2025 Damien P. George

The MIT License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
