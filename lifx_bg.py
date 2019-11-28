# -*- coding: utf-8 -*-
#!/usr/bin/env python

"""
lifx_bg.py
a circadian light controller and interface for LIFX HTTP API v1
@author: Noah Norman
n@hardwork.party


TO DO:
• HTTP BYPASS SWITCH
• CONFIRM SWITCH RESPONSE
• ARGUMENTS / JSON in data.json FOR ALL or SPECIFIC LIGHT NAMES
"""

import json
import time

import socket
import tornado.websocket
import tornado.httpserver
import tornado.ioloop
from tornado import gen

import os
import argparse
import locale
import subprocess
import sys

from lightsc import LightsClient

import log
import lut
import config

PORT = 8888
CONTROLLERS = []
LUT = lut.Lut();

def init_lights():
    try:
        lightsdrundir = subprocess.check_output(["lightsd", "--rundir"])
    except Exception as ex:
        print(
            "Couldn't infer lightsd's runtime directory, is lightsd installed? "
            "({})\nTrying build/socket...".format(ex),
            file=sys.stderr
        )
        lightscdir = os.path.realpath(__file__).split(os.path.sep)[:-2]
        lightsdrundir = os.path.join(*[os.path.sep] + lightscdir + ["build"])
    else:
        encoding = locale.getpreferredencoding()
        lightsdrundir = lightsdrundir.decode(encoding).strip()

    url = "unix://" + os.path.join(lightsdrundir, "socket")

    try:
        print("Connecting to lightsd@{}".format(url))
        return LightsClient(url)

    except Exception as ex:
        print(
            "Couldn't connect to {}, is the url correct "
            "and is lightsd running? ({})".format(url, ex),
            file=sys.stderr
        )
        sys.exit(1)

class IndexHandler(tornado.web.RequestHandler):
    """HTTP request handler to serve HTML for switch server"""
    def get(self):
        self.render('switch/index.html')

class SwitchWSHandler(tornado.websocket.WebSocketHandler):
    """Communicates switch commands with the switch web view"""
    def open(self):
#        self.set_header("Access-Control-Allow-Origin", '*')
        inf('new connection to switch, sending power state')
        msg = controller_pwr_msg()
        self.write_message(msg)
        CONTROLLERS.append(self)

    def on_message(self, message):
        inf('SWITCH message received: {msg}'.format(msg=message))
        if message == 'ON' or message == 'on':
            switch('on', True)
        elif message == 'OFF' or message == 'off':
            switch('off', True)
        else:
            inf('UNUSABLE MESSAGE FROM SWITCH')

    def on_close(self):
        inf('connection closed')
        CONTROLLERS.remove(self)

    def check_origin(self, origin):
        return True

def controller_pwr_msg():
    return "{ \"power_on\": \"%s\" }" % (is_on())

def update_controller_pwr_states():
    for con in CONTROLLERS:
        con.write_message(controller_pwr_msg())

def inf(msg):
    logger.info(msg)

def dbg(msg):
    logger.debug(msg)

def test_connection():
    response_json = get_states()
    inf('TESTING.......')
    inf('-----------------')
    for num, rsp in enumerate(response_json):
        inf('-------- LIGHT NUM: ' + str(num) + ' ---------')
        inf('-------- NAME: ' + str(rsp[u'label']) + ' --------')
        inf('-------- COLOR: ' + str(rsp[u'hsbk']) + ' ---------')
        inf('-------- POWER:  ' + bool2str(rsp[u'power']) + ' ---------')
        inf('///////////')
    dbg(power_state())

def is_on():
    if power_state() == 'on':
        return True
    else:
        return False

def bool2str(b):
    return 'on' if b == True else 'off'

def power_state():
    """ assumes all lights share the same state """
    result = get_states()
    return result[0][u'power']

def get_states(target='*'):
    response = ldc.get_light_state(target)
    return response[u'result']

@gen.coroutine
def switch(pwr, from_controller):
    if from_controller:
        inf('received power switch from controller, switching {p}'.format(p=pwr))
    else:
        inf('notifying controller of power state switch {p}'.format(p=pwr))
        update_controller_pwr_states()
    c_st = LUT.state_now()
    if pwr == 'on':
        t = config.fade_in()
    else:
        t = config.fade_out()
    set_all_to_hsbkdp(c_st.hue, c_st.sat, c_st.bright,
                      c_st.kelvin, t, pwr)
    # that command broke the existing transition so we have to put a new one
    yield gen.sleep(t)
    # yield gen.Task(tornado.ioloop.IOLoop.instance().add_timeout, time.time() + t)
    goto_next_state()

def goto_next_state():
    nxt_st = LUT.next_state()
    t = LUT.secs_to_next_state()

    inf('transitioning to:          ' + str(nxt_st.name))
    inf('over:                      ' + str(t))

    set_all_to_hsbkdp(nxt_st.hue, nxt_st.sat, nxt_st.bright, nxt_st.kelvin, t)
    go_next_in(t+1)


@gen.coroutine
def go_next_in(t):
    inf('WAITING {s}s TO NEXT TRANSITION'.format(s=t))
    yield gen.sleep(t)
    # yield gen.Task(tornado.ioloop.IOLoop.instance().add_timeout, time.time() + t)
    goto_next_state()

def set_all_to_hsbkdp(h, s, b, k, t, pwr=None, target='*'):
    if pwr == None:
        pwr = power_state()
    if pwr == 'off':
        b = 0

    ldc.set_light_from_hsbk(target, h, s, b, k, t)

ldc = init_lights()

logger = log.make_logger()
inf('<<<<<<<<<<<<<<<<<< SYSTEM RESTART >>>>>>>>>>>>>>>>>>>>>')

test_connection()

# update sunrise / sunset every day
MS_DAY = 60 * 60 * 24 * 1000
refresh_solar_info = tornado.ioloop.PeriodicCallback(LUT.refresh_solar(),                                                     MS_DAY)
refresh_solar_info.start()


switch('on', False)
print('state now: ' + str(LUT.state_now()))
print('next state: ' + str(LUT.next_state()))
print('secs to next state: ' + str(LUT.secs_to_next_state()))


application = tornado.web.Application(
    handlers=[
        (r"/", IndexHandler),
        (r"/ws", SwitchWSHandler),
    ])

http_server = tornado.httpserver.HTTPServer(application)
http_server.listen(PORT)
my_ip = socket.gethostbyname(socket.gethostname())
inf('*** Server Started at {ip} ***'.format(ip=my_ip))
inf('*** Server listening on port {port} ****'.format(port=PORT))

# if you want to cancel this, hang on to next_timeout for cancel_timeout
#next_timeout = tornado.ioloop.IOLoop.instance().add_timeout(
#    datetime.timedelta(seconds=5), begin_from(config.LOC_LUT))


tornado.ioloop.IOLoop.instance().start()



#CONSIDER DOING A BREATHE EFFECT FOR EASE-IN EASE-OUT
