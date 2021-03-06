#Copyright (c) 2008, Media Modifications Ltd.

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import gtk
import gobject
import os
import shutil
import telepathy
import telepathy.client
import logging
import xml.dom.minidom
import time
from xml.dom.minidom import parse
import pygst
pygst.require('0.10')
import gst

import logging
logger = logging.getLogger('record:record.py')

from sugar.activity import activity
from sugar.presence import presenceservice
from sugar.presence.tubeconn import TubeConnection
from sugar import util
import port.json

from model import Model
from ui import UI
from recordtube import RecordTube
from glive import Glive
from glivex import GliveX
from gplay import Gplay
from greplay import Greplay
from recorded import Recorded
from constants import Constants
import instance
from instance import Instance
import serialize
import utils


gst.debug_set_active(True)
gst.debug_set_colored(False)
if logging.getLogger().level <= logging.DEBUG:
    gst.debug_set_default_threshold(gst.LEVEL_WARNING)
else:
    gst.debug_set_default_threshold(gst.LEVEL_ERROR)


class Record(activity.Activity):

    log = logging.getLogger('record-activity')

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        #flags for controlling the writing to the datastore
        self.I_AM_CLOSING = False
        self.I_AM_SAVED = False

        self.props.enable_fullscreen_mode = False
        Instance(self)
        Constants(self)
        self.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )

        #wait a moment so that our debug console capture mistakes
        gobject.idle_add( self._initme, None )


    def _initme( self, userdata=None ):
        #totally tubular
        self.meshTimeoutTime = 10000
        self.recTube = None
        self.connect( "shared", self._sharedCb )

        #the main classes
        self.m = Model(self)
        self.glive = Glive(self)
        self.glivex = GliveX(self)
        self.gplay = Gplay(self)
        self.ui = UI(self)

        #CSCL
        if self._shared_activity:
            #have you joined or shared this activity yourself?
            if self.get_shared():
                self._meshJoinedCb( self )
            else:
                self.connect("joined", self._meshJoinedCb)

        return False


    def read_file(self, file):
        try:
            dom = parse(file)
        except Exception, e:
            logger.error('read_file: %s' % e)
            return

        serialize.fillMediaHash(dom, self.m.mediaHashs)

        for i in dom.documentElement.getElementsByTagName('ui'):
            for ui_el in i.childNodes:
                self.ui.deserialize(port.json.loads(ui_el.data))


    def write_file(self, file):
        self.I_AM_SAVED = False

        self.m.mediaHashs['ui'] = self.ui.serialize()

        dom = serialize.saveMediaHash(self.m.mediaHashs)

        ui_data = port.json.dumps(self.ui.serialize())
        ui_el = dom.createElement('ui')
        ui_el.appendChild(dom.createTextNode(ui_data))
        dom.documentElement.appendChild(ui_el)

        xmlFile = open( file, "w" )
        dom.writexml(xmlFile)
        xmlFile.close()

        allDone = True
        for h in range (0, len(self.m.mediaHashs)-1):
            mhash = self.m.mediaHashs[h]
            for i in range (0, len(mhash)):
                recd = mhash[i]

                if ( (not recd.savedMedia) or (not recd.savedXml) ):
                    allDone = False

                if (self.I_AM_CLOSING):
                    mediaObject = recd.datastoreOb
                    if (mediaObject != None):
                        recd.datastoreOb = None
                        mediaObject.destroy()
                        del mediaObject

        self.I_AM_SAVED = True
        if (self.I_AM_SAVED and self.I_AM_CLOSING):
            self.destroy()


    def stopPipes(self):
        self.ui.doMouseListener( False )
        self.m.setUpdating( False )

        if (self.ui.COUNTINGDOWN):
            self.m.abandonRecording()
        elif (self.m.RECORDING):
            self.m.doShutter()
        else:
            self.glive.stop()
            self.glivex.stop()


    def restartPipes(self):
        if (not self.ui.TRANSCODING):
            self.ui.updateModeChange( )
            self.ui.doMouseListener( True )


    def close( self ):
        self.I_AM_CLOSING = True

        self.m.UPDATING = False
        if (self.ui != None):
            self.ui.updateButtonSensitivities( )
            self.ui.doMouseListener( False )
            self.ui.hideAllWindows()
        if (self.gplay != None):
            self.gplay.stop( )
        if (self.glive != None):
            self.glive.stop( )
        if self.glivex != None:
            self.glivex.stop()

        #this calls write_file
        activity.Activity.close( self )


    def destroy( self ):
        if self.I_AM_SAVED:
            activity.Activity.destroy( self )


    def _sharedCb( self, activity ):
        self._setup()

        id = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube( Constants.SERVICE, {})


    def _meshJoinedCb( self, activity ):
        if not self._shared_activity:
            return

        self._setup()

        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes( reply_handler=self._list_tubes_reply_cb, error_handler=self._list_tubes_error_cb)


    def _list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self._newTubeCb(*tube_info)


    def _list_tubes_error_cb(self, e):
        self.__class__.log.error('ListTubes() failed: %s', e)


    def _setup(self):
        #sets up the tubes...
        if self._shared_activity is None:
            self.__class__.log.error('_setup: Failed to share or join activity')
            return

        pservice = presenceservice.get_instance()
        try:
            name, path = pservice.get_preferred_connection()
            self.conn = telepathy.client.Connection(name, path)
        except:
            self.__class__.log.error('_setup: Failed to get_preferred_connection')

        # Work out what our room is called and whether we have Tubes already
        bus_name, conn_path, channel_paths = self._shared_activity.get_channels()
        room = None
        tubes_chan = None
        text_chan = None
        for channel_path in channel_paths:
            channel = telepathy.client.Channel(bus_name, channel_path)
            htype, handle = channel.GetHandle()
            if htype == telepathy.HANDLE_TYPE_ROOM:
                self.__class__.log.debug('Found our room: it has handle#%d "%s"', handle, self.conn.InspectHandles(htype, [handle])[0])
                room = handle
                ctype = channel.GetChannelType()
                if ctype == telepathy.CHANNEL_TYPE_TUBES:
                    self.__class__.log.debug('Found our Tubes channel at %s', channel_path)
                    tubes_chan = channel
                elif ctype == telepathy.CHANNEL_TYPE_TEXT:
                    self.__class__.log.debug('Found our Text channel at %s', channel_path)
                    text_chan = channel

        if room is None:
            self.__class__.log.error("Presence service didn't create a room")
            return
        if text_chan is None:
                self.__class__.log.error("Presence service didn't create a text channel")
                return

        # Make sure we have a Tubes channel - PS doesn't yet provide one
        if tubes_chan is None:
            self.__class__.log.debug("Didn't find our Tubes channel, requesting one...")
            tubes_chan = self.conn.request_channel(telepathy.CHANNEL_TYPE_TUBES, telepathy.HANDLE_TYPE_ROOM, room, True)

        self.tubes_chan = tubes_chan
        self.text_chan = text_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube', self._newTubeCb)


    def _newTubeCb(self, id, initiator, type, service, params, state):
        self.__class__.log.debug('New tube: ID=%d initator=%d type=%d service=%s params=%r state=%d', id, initiator, type, service, params, state)
        if (type == telepathy.TUBE_TYPE_DBUS and service == Constants.SERVICE):
            if state == telepathy.TUBE_STATE_LOCAL_PENDING:
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(id)
            tube_conn = TubeConnection(self.conn, self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES], id, group_iface=self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP])
            self.recTube = RecordTube(tube_conn)
            self.recTube.connect("new-recd", self._newRecdCb)
            self.recTube.connect("recd-request", self._recdRequestCb)
            self.recTube.connect("recd-bits-arrived", self._recdBitsArrivedCb)
            self.recTube.connect("recd-unavailable", self._recdUnavailableCb)


    def _newRecdCb( self, objectThatSentTheSignal, recorder, xmlString ):
        self.__class__.log.debug('_newRecdCb')
        dom = None
        try:
            dom = xml.dom.minidom.parseString(xmlString)
        except:
            self.__class__.log.error('Unable to parse mesh xml')
        if (dom == None):
            return

        recd = Recorded()
        recd = serialize.fillRecdFromNode(recd, dom.documentElement)
        if (recd != None):
            self.__class__.log.debug('_newRecdCb: adding new recd thumb')
            recd.buddy = True
            recd.downloadedFromBuddy = False
            self.m.addMeshRecd( recd )
        else:
            self.__class__.log.debug('_newRecdCb: recd is None. Unable to parse XML')


    def requestMeshDownload( self, recd ):
        if (recd.meshDownloading):
            return True

        self.m.updateXoFullStatus()
        if (self.m.FULL):
            return True

        #this call will get the bits or request the bits if they're not available
        if (recd.buddy and (not recd.downloadedFromBuddy)):
            self.meshInitRoundRobin(recd)
            return True

        else:
            return False


    def meshInitRoundRobin( self, recd ):
        if (recd.meshDownloading):
            self.__class__.log.debug("meshInitRoundRobin: we are in midst of downloading this file...")
            return

        if (self.recTube == None):
            gobject.idle_add(self.ui.updateMeshProgress, False, recd)
            return

        #start with who took the photo
        recd.triedMeshBuddies = []
        recd.triedMeshBuddies.append(Instance.keyHashPrintable)
        self.meshReqRecFromBuddy( recd, recd.recorderHash, recd.recorderName )


    def meshNextRoundRobinBuddy( self, recd ):
        self.__class__.log.debug('meshNextRoundRobinBuddy')
        if (recd.meshReqCallbackId != 0):
            gobject.source_remove(recd.meshReqCallbackId)
            recd.meshReqCallbackId = 0

        #delete any stub of a partially downloaded file
        filepath = recd.getMediaFilepath()
        if (filepath != None):
            if (os.path.exists(filepath)):
                os.remove( filepath )

        goodBudObj = None
        buds = self._shared_activity.get_joined_buddies()
        for i in range (0, len(buds)):
            nextBudObj = buds[i]
            nextBud = util._sha_data(nextBudObj.props.key)
            nextBud = util.printable_hash(nextBud)
            if (recd.triedMeshBuddies.count(nextBud) > 0):
                self.__class__.log.debug('mnrrb: weve already tried bud ' + str(nextBudObj.props.nick))
            else:
                self.__class__.log.debug('mnrrb: ask next buddy: ' + str(nextBudObj.props.nick))
                goodBudObj = nextBudObj
                break

        if (goodBudObj != None):
            goodNick = goodBudObj.props.nick
            goodBud = util._sha_data(goodBudObj.props.key)
            goodBud = util.printable_hash(goodBud)
            self.meshReqRecFromBuddy(recd, goodBud, goodNick)
        else:
            self.__class__.log.debug('weve tried all buddies here, and no one has this recd')
            recd.meshDownloading = False
            recd.triedMeshBuddies = []
            recd.triedMeshBuddies.append(Instance.keyHashPrintable)
            self.ui.updateMeshProgress(False, recd)


    def meshReqRecFromBuddy( self, recd, fromWho, fromWhosNick ):
        recd.triedMeshBuddies.append( fromWho )
        recd.meshDownloadingFrom = fromWho
        recd.meshDownloadingFromNick = fromWhosNick
        recd.meshDownloadingProgress = False
        recd.meshDownloading = True
        recd.meshDownlodingPercent = 0.0
        self.ui.updateMeshProgress(True, recd)
        recd.meshReqCallbackId = gobject.timeout_add(self.meshTimeoutTime, self._meshCheckOnRecdRequest, recd)
        self.recTube.requestRecdBits( Instance.keyHashPrintable, fromWho, recd.mediaMd5 )


    def _meshCheckOnRecdRequest( self, recdRequesting ):
        #todo: add category for "not active activity, so go ahead and delete"

        if (recdRequesting.downloadedFromBuddy):
            self.__class__.log.debug('_meshCheckOnRecdRequest: recdRequesting.downloadedFromBuddy')
            if (recdRequesting.meshReqCallbackId != 0):
                gobject.source_remove(recdRequesting.meshReqCallbackId)
                recdRequesting.meshReqCallbackId = 0
            return False
        if (recdRequesting.deleted):
            self.__class__.log.debug('_meshCheckOnRecdRequest: recdRequesting.deleted')
            if (recdRequesting.meshReqCallbackId != 0):
                gobject.source_remove(recdRequesting.meshReqCallbackId)
                recdRequesting.meshReqCallbackId = 0
            return False
        if (recdRequesting.meshDownloadingProgress):
            self.__class__.log.debug('_meshCheckOnRecdRequest: recdRequesting.meshDownloadingProgress')
            #we've received some bits since last we checked, so keep waiting...  they'll all get here eventually!
            recdRequesting.meshDownloadingProgress = False
            return True
        else:
            self.__class__.log.debug('_meshCheckOnRecdRequest: ! recdRequesting.meshDownloadingProgress')
            #that buddy we asked info from isn't responding; next buddy!
            #self.meshNextRoundRobinBuddy( recdRequesting )
            gobject.idle_add(self.meshNextRoundRobinBuddy, recdRequesting)
            return False


    def _recdRequestCb( self, objectThatSentTheSignal, whoWantsIt, md5sumOfIt ):
        #if we are here, it is because someone has been told we have what they want.
        #we need to send them that thing, whatever that thing is
        recd = self.m.getRecdByMd5( md5sumOfIt )
        if (recd == None):
            self.__class__.log.debug('_recdRequestCb: we dont have the recd they asked for')
            self.recTube.unavailableRecd(md5sumOfIt, Instance.keyHashPrintable, whoWantsIt)
            return
        if (recd.deleted):
            self.__class__.log.debug('_recdRequestCb: we have the recd, but it has been deleted, so we wont share')
            self.recTube.unavailableRecd(md5sumOfIt, Instance.keyHashPrintable, whoWantsIt)
            return
        if (recd.buddy and not recd.downloadedFromBuddy):
            self.__class__.log.debug('_recdRequestCb: we have an incomplete recd, so we wont share')
            self.recTube.unavailableRecd(md5sumOfIt, Instance.keyHashPrintable, whoWantsIt)
            return

        recd.meshUploading = True
        filepath = recd.getMediaFilepath()

        if (recd.type == Constants.TYPE_AUDIO):
            audioImgFilepath = recd.getAudioImageFilepath()

            destPath = os.path.join(Instance.instancePath, "audioBundle")
            destPath = utils.getUniqueFilepath(destPath, 0)
            cmd = "cat " + str(filepath) + " " + str(audioImgFilepath) + " > " + str(destPath)
            self.__class__.log.debug(cmd)
            os.system(cmd)
            filepath = destPath

        sent = self.recTube.broadcastRecd(recd.mediaMd5, filepath, whoWantsIt)
        recd.meshUploading = False
        #if you were deleted while uploading, now throw away those bits now
        if (recd.deleted):
            recd.doDeleteRecorded(recd)


    def _recdBitsArrivedCb( self, objectThatSentTheSignal, md5sumOfIt, part, numparts, bytes, fromWho ):
        #self.__class__.log.debug('_recdBitsArrivedCb: ' + str(part) + "/" + str(numparts))
        recd = self.m.getRecdByMd5( md5sumOfIt )
        if (recd == None):
            self.__class__.log.debug('_recdBitsArrivedCb: thx 4 yr bits, but we dont even have that photo')
            return
        if (recd.deleted):
            self.__class__.log.debug('_recdBitsArrivedCb: thx 4 yr bits, but we deleted that photo')
            return
        if (recd.downloadedFromBuddy):
            self.__class__.log.debug('_recdBitsArrivedCb: weve already downloadedFromBuddy')
            return
        if (not recd.buddy):
            self.__class__.log.debug('_recdBitsArrivedCb: uh, we took this photo, so dont need your bits')
            return
        if (recd.meshDownloadingFrom != fromWho):
            self.__class__.log.debug('_recdBitsArrivedCb: wrong bits ' + str(fromWho) + ", exp:" + str(recd.meshDownloadingFrom))
            return

        #update that we've heard back about this, reset the timeout
        gobject.source_remove(recd.meshReqCallbackId)
        recd.meshReqCallbackId = gobject.timeout_add(self.meshTimeoutTime, self._meshCheckOnRecdRequest, recd)

        #update the progress bar
        recd.meshDownlodingPercent = (part+0.0)/(numparts+0.0)
        recd.meshDownloadingProgress = True
        self.ui.updateMeshProgress(True, recd)
        f = open(recd.getMediaFilepath(), 'a+')
        f.write(bytes)
        f.close()

        if part == numparts:
            self.__class__.log.debug('Finished receiving %s' % recd.title)
            gobject.source_remove( recd.meshReqCallbackId )
            recd.meshReqCallbackId = 0
            recd.meshDownloading = False
            recd.meshDownlodingPercent = 1.0
            recd.downloadedFromBuddy = True
            if (recd.type == Constants.TYPE_AUDIO):
                filepath = recd.getMediaFilepath()
                bundlePath = os.path.join(Instance.instancePath, "audioBundle")
                bundlePath = utils.getUniqueFilepath(bundlePath, 0)

                cmd = "split -a 1 -b " + str(recd.mediaBytes) + " " + str(filepath) + " " + str(bundlePath)
                self.__class__.log.debug( cmd )
                os.system( cmd )

                bundleName = os.path.basename(bundlePath)
                mediaFilename = str(bundleName) + "a"
                mediaFilepath = os.path.join(Instance.instancePath, mediaFilename)
                mediaFilepathExt = os.path.join(Instance.instancePath, mediaFilename+".ogg")
                os.rename(mediaFilepath, mediaFilepathExt)
                audioImageFilename = str(bundleName) + "b"
                audioImageFilepath = os.path.join(Instance.instancePath, audioImageFilename)
                audioImageFilepathExt = os.path.join(Instance.instancePath, audioImageFilename+".png")
                os.rename(audioImageFilepath, audioImageFilepathExt)

                recd.mediaFilename = os.path.basename(mediaFilepathExt)
                recd.audioImageFilename = os.path.basename(audioImageFilepathExt)

            self.ui.showMeshRecd( recd )
        elif part > numparts:
            self.__class__.log.error('More parts than required have arrived')


    def _getAlbumArtCb( self, objectThatSentTheSignal, pixbuf, recd ):

        if (pixbuf != None):
            imagePath = os.path.join(Instance.instancePath, "audioPicture.png")
            imagePath = utils.getUniqueFilepath( imagePath, 0 )
            pixbuf.save( imagePath, "png", {} )
            recd.audioImageFilename = os.path.basename(imagePath)

        self.ui.showMeshRecd( recd )
        return False


    def _recdUnavailableCb( self, objectThatSentTheSignal, md5sumOfIt, whoDoesntHaveIt ):
        self.__class__.log.debug('_recdUnavailableCb: sux, we want to see that photo')
        recd = self.m.getRecdByMd5( md5sumOfIt )
        if (recd == None):
            self.__class__.log.debug('_recdUnavailableCb: actually, we dont even know about that one..')
            return
        if (recd.deleted):
            self.__class__.log.debug('_recdUnavailableCb: actually, since we asked, we deleted.')
            return
        if (not recd.buddy):
            self.__class__.log.debug('_recdUnavailableCb: uh, odd, we took that photo and have it already.')
            return
        if (recd.downloadedFromBuddy):
            self.__class__.log.debug('_recdUnavailableCb: we already downloaded it...  you might have been slow responding.')
            return
        if (recd.meshDownloadingFrom != whoDoesntHaveIt):
            self.__class__.log.debug('_recdUnavailableCb: we arent asking you for a copy now.  slow response, pbly.')
            return

        #self.meshNextRoundRobinBuddy( recd )
