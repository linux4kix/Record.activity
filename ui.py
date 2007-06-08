from sugar.graphics.toolbutton import ToolButton

from color import Color
from polygon import Polygon

class UI:

	def __init__( self, pca ):
		self.ca = pca
		self.loadColors()
		self.loadGfx()

		#this includes the default sharing tab
		toolbox = activity.ActivityToolbox(self)
		self.set_toolbox(toolbox)
		toolbar = CToolbar(self.c)
		toolbox.add_toolbar( ('Camera'), toolbar)
		toolbox.show()

		#two pipelines, connected by bloodlust
		self.newGlive(False, False)
		self.newGplay()

		mainBox = Gtk.VBox()
		self.set_canvas(mainBox)
		topBox = Gtk.HBox()
		mainBox.pack_start(topBox)
		#insert entry fields on left
		infoBox = Gtk.VBox()
		mainBox.pack_start(infoBox)
		self.nameField = gtk.Button()
		infoBox.pack_start(self.nameField)
		self.photographerField = gtk.Button()
		infoBox.pack_start(self.photographerField)
		self.tagField = gtk.Button()
		infoBox.pack_start(self.tagField)
		self.shutterField = gtk.Button()
		infoBox.pack_start(self.shutterField)

		#video, scrubber etc on right
		videoBox = Gtk.VBox()
		#blank space for video and info gfx
		self.videoSpace = gtk.Button()
		videoBox.pack_start(self.videoSpace)
		self.videoScrubber = gtk.Button()
		videoBox.pack_start(self.videoScrubber)

		thumbnailsBox = Gtk.HBox()
		mainBox.pack_end(thumbnailsBox)
		self.leftThumbButton = gtk.Button()
		thumbnailsBox.pack_start( self.leftThumbButton )
		self.thumbButts = []
		for i in range (0, 7):
			thumbButt = gtk.Button()
			thumbButt.callback( i )
			thumbnailsBox.pack_start( thumbButt )
			thumbButts[i] = thumbButt
		self.rightThumbButton = gtk.Button()
		thumbnailsBox.pack_start( self.rightThumbButton )
		self.show_all()


	def showVid( self, vidPath = None ):
		if (vidPath != None):
			self.UPDATING = True
			self._frame.setWaitCursor()

			self._img = self.modWaitImg
			self.SHOW = self.SHOW_PLAY
			self._id.redraw()

			self._livevideo.hide()
			self._livevideo.playa.stop()
			self._playvideo.show()
			vp = "file://" + vidPath
			self._playvideo.playa.setLocation(vp)
			self._frame.setDefaultCursor()
			self.UPDATING = False


	def showImg( self, imgPath ):
		self.SHOW = self.SHOW_STILL

		if (self._img == None):
			self._livevideo.hide()
			self._playvideo.hide()

		pixbuf = gtk.gdk.pixbuf_new_from_file(imgPath)
		self._img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)
		self._id.redraw()


	#cursor control
	def setWaitCursor( self ):
		self.window.set_cursor( gtk.gdk.Cursor(gtk.gdk.WATCH) )

	def setDefaultCursor( self ):
		self.window.set_cursor( None )

	def loadGfx( self ):
		#load svgs
		polSvg_f = open(os.path.join(self._basepath, 'polaroid.svg'), 'r')
		polSvg_d = polSvg_f.read()
		polSvg_f.close()
		self.polSvg = self.loadSvg( polSvg_d, None, None )

		camSvg_f = open(os.path.join(self._basepath, 'shutter_button.svg'), 'r')
		camSvg_d = camSvg_f.read()
		camSvg_f.close()
		self.camSvg = self.loadSvg( camSvg_d, None, None )

		camInvSvg_f = open( os.path.join(self._basepath, 'shutter_button_invert.svg'), 'r')
		camInvSvg_d = camInvSvg_f.read()
		camInvSvg_f.close()
		self.camInvSvg = self.loadSvg(camInvSvg_d, None, None)

		camRecSvg_f = open(os.path.join(self._basepath, 'shutter_button_record.svg'), 'r')
		camRecSvg_d = camRecSvg_f.read()
		camRecSvg_f.close()
		self.camRecSvg = self.loadSvg( camRecSvg_d, None, None)

		self.nickName = profile.get_nick_name()

		#sugar colors, replaced with b&w b/c of xv issues
		color = profile.get_color()
		fill = color.get_fill_color()
		stroke = color.get_stroke_color()
		self.colorFill = self._colWhite._hex
		self.colorStroke = self._colBlack._hex

		butPhoSvg_f = open(os.path.join(self._basepath, 'thumb_photo.svg'), 'r')
		butPhoSvg_d = butPhoSvg_f.read()
		self.thumbPhotoSvg = self.loadSvg(butPhoSvg_d, self.colorStroke, self.colorFill)
		butPhoSvg_f.close()

		butVidSvg_f = open(os.path.join(self._basepath, 'thumb_video.svg'), 'r')
		butVidSvg_d = butVidSvg_f.read()
		self.thumbVideoSvg = self.loadSvg(butVidSvg_d, self.colorStroke, self.colorFill)
		butVidSvg_f.close()

		closeSvg_f = open(os.path.join(self._basepath, 'thumb_close.svg'), 'r')
		closeSvg_d = closeSvg_f.read()
		self.closeSvg = self.loadSvg(closeSvg_d, self.colorStroke, self.colorFill)
		closeSvg_f.close()

		menubarPhoto_f = open( os.path.join(self._basepath, 'menubar_photo.svg'), 'r' )
		menubarPhoto_d = menubarPhoto_f.read()
		self.menubarPhoto = self.loadSvg( menubarPhoto_d, self._colWhite._hex, self._colMenuBar._hex )
		menubarPhoto_f.close()

		menubarVideo_f = open( os.path.join(self._basepath, 'menubar_video.svg'), 'r' )
		menubarVideo_d = menubarVideo_f.read()
		self.menubarVideo = self.loadSvg( menubarVideo_d, self._colWhite._hex, self._colMenuBar._hex)
		menubarVideo_f.close()

		self.modVidF = os.path.join(self._basepath, 'mode_video.png')
		modVidPB = gtk.gdk.pixbuf_new_from_file(self.modVidF)
		self.modVidImg = _camera.cairo_surface_from_gdk_pixbuf(modVidPB)

		modPhoF = os.path.join(self._basepath, 'mode_photo.png')
		modPhoPB = gtk.gdk.pixbuf_new_from_file(modPhoF)
		self.modPhoImg = _camera.cairo_surface_from_gdk_pixbuf(modPhoPB)

		modWaitF = os.path.join(self._basepath, 'mode_wait.png')
		modWaitPB = gtk.gdk.pixbuf_new_from_file(modWaitF)
		self.modWaitImg = _camera.cairo_surface_from_gdk_pixbuf(modWaitPB)

		modDoneF = os.path.join(self._basepath, 'mode_restart.png')
		modDonePB = gtk.gdk.pixbuf_new_from_file(modDoneF)
		self.modDoneImg = _camera.cairo_surface_from_gdk_pixbuf(modDonePB)

		#reset there here for uploading to server
		self.fill = color.get_fill_color()
		self.stroke = color.get_stroke_color()
		key = profile.get_pubkey()
		key_hash = util._sha_data(key)
		self.hashed_key = util.printable_hash(key_hash)

	def loadColors( self ):
		self._colBlack = Color( 0, 0, 0, 255 )
		self._colWhite = Color( 255, 255, 255, 255 )
		self._colRed = Color( 255, 0, 0, 255 )
		self._colThumbTray = Color( 255, 255, 255, 255 )
		self._colMenuBar = Color( 0, 0, 0, 255 )

	def loadSvg( self, data, stroke, fill ):
		if ((stroke == None) or (fill == None)):
			return rsvg.Handle( data=data )

		entity = '<!ENTITY fill_color "%s">' % fill
		data = re.sub('<!ENTITY fill_color .*>', entity, data)

		entity = '<!ENTITY stroke_color "%s">' % stroke
		data = re.sub('<!ENTITY stroke_color .*>', entity, data)

		return rsvg.Handle( data=data )




class CToolbar(gtk.Toolbar):
	def __init__(self, pc):
		gtk.Toolbar.__init__(self)
		self.c = pc


		picButt = ToolButton( os.path.join(self.gfxPath, "menubar_photo.svg" ) )
		picButt.props.sensitive = True
		picButt.connect('clicked', self._mode_pic_cb)
		self.insert(picButt, -1)
		picButt.show()

		vidButt = ToolButton( os.path.join(self.gfxPath, "menubar_video.svg" ) )
		vidButt.props.sensitive = True
		vidButt.connect('clicked', self._mode_vid_cb)
		self.insert(vidButt, -1)
		vidButt.show()

#		picMeshButt = ToolButton('go-next')
#		picMeshButt.props.sensitive = True
#		picMeshButt.connect('clicked', self._mode_picmesh_cb)
#		self.insert(picMeshButt, -1)
#		picMeshButt.show()

#		vidMeshButt = ToolButton('go-previous')
#		vidMeshButt.props.sensitive = True
#		vidMeshButt.connect('clicked', self._mode_vidmesh_cb)
#		self.insert(vidMeshButt, -1)
#		vidMeshButt.show()

	def _mode_vid_cb(self, button):
		self.c.doVideoMode()

	def _mode_pic_cb(self, button):
		self.c.doPhotoMode()
