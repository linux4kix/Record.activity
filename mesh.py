from sugar.p2p import network
from sugar.presence import presenceservice
import urlparse
import urllib
import posixpath

xmlRpcPort = 8888
httpPort = 8889

class MeshXMLRPCServer:
	def __init__( self, pc ):
		self.c = pc

		#this is ye olde xmlrpc server
		#listen to and talk through this port for xmlrpc, using this here info
		self.server = network.GlibXMLRPCServer(("", xmlRpcPort))
		self.server.register_instance(self) #anything witout an _ is callable by all the hos and joes out there

	def newPicNotice( self, arg1, arg2=None ):
		print "Request got " + str(arg1) + ", " + str(arg2)
		return "successios"


class HttpServer(network.GlibTCPServer):
	def __init__(self, pc):
		self.c = pc
		self.rootpath = self.c.journalPath
		server_address = ("", httpPort)
		network.GlibTCPServer.__init__(self, server_address, HttpReqHandler);


class HttpReqHandler(network.ChunkedGlibHTTPRequestHandler):
	#path is url to the path to the file being requested
	def translate_path(self, path):
		print( "a: ", path )

		url = urlparse.urlparse(path)[2]
		params = urlparse.urlparse(path)[4]
		print( "url:", url )
		print( "params:", params )

		urlPath = posixpath.normpath(urllib.unquote(url))
		urlPathAy = path.split('/')
		urlPathAy = filter(None, urlPathAy)
		print( "urlPathAy: ", urlPathAy )

		#do some logic here to figure out what to do next

		#take a looksee at this coolness from our superclass (which is persistant mofo above..
		#who is always here whenever i wake up)
		print( "rootpath: ", self.server.rootpath )

		self.send_response(200)
		#self.send_header("Content-type", "jpeg/jpg")
		#self.send_header("Content-Disposition", 'attachment; filename="' + str(self.server.c.modFile) )

		#should be abs path... check it 1st
		fileToSend = self.server.c.modVidF
		return fileToSend




class MeshClient:

	def __init__( self, pc ):
		self.c = pc

		#stay alert!  buddies might show up at any time!
		print("1 meshClient");
		print("1.1 meshClient: ", self.c._frame)
		self.my_acty = self.c._frame._shared_activity  #_pservice.get_activity(self.c.activity_id)
		print("1.2 meshClient: ", self.my_acty)
		#self.my_acty_id = self.c._frame.activity_id
		#print( "uid:", self.my_acty_id )

		self.my_acty.connect('buddy-joined', self.buddy_joined_cb)
		print("1.3")
		self.my_acty.connect('buddy-left', self.buddy_left_cb)
		print("1.4")

		print("1.5", len(self.my_acty.get_joined_buddies()) )
		#if you've just arrived at the playground, take a peruse around
		for buddy in self.my_acty.get_joined_buddies():
			print ("a", buddy.props.nick)
			print ("a", buddy.props.ip4_address)
			print ("a", buddy.props.owner) #me boolean

		print("1.6")

	def buddy_joined_cb( self, activity, buddy ):
		print ("b", buddy.props.nick)
		print ("b", buddy.props.ip4_address)
		print ("b", buddy.props.owner) #me boolean

	def buddy_left_cb( self, activity, buddy ):
		print ("c", buddy.props.nick)
		print ("c", buddy.props.ip4_address)
		print ("c", buddy.props.owner) #me boolean

	#herein we notify our buddies of some cool stuff we got going on they mights wants to knows abouts
	def notifyBudsOfNewPic( self ):
		for buddy in self.my_acty.get_joined_buddies():
			bud = network.GlibServerProxy( "http://%s:%d" % (buddy.props.ip4_address, xmlRpcPort))
			bud.newPicNotice("bar", reply_handler=self.notifyBudsOfNewPic_cb,
									error_handler=self.error_cb, user_data=bud)

	def notifyBudsOfNewPic_cb(self, response, bud):
		print "Response was %s, user_data was %s" % (response, user_data)

	def error_cb(self, error, bud):
		print "We've a no go erroro! ", bud

	def reqNewPhotoBits(self):
		#check i am not me, iterate till you get another dude
		bud = self.my_acty.get_joined_buddies()[0]
		getter = network.GlibURLDownloader("http://" + str(bud.props.ip4_address) + ":" + str(httpPort) + "/getStuff")
		getter.connect( "finished", self._download_result_cb, bud )
		getter.connect( "error", self._download_error_cb, bud )
		getter.start()

	def _download_result_cb(self, getter, tempfile, suggested_name, buddy):
		dest = os.path.join(os.path.expanduser("~"), suggested_name)
		shutil.copyfile(tempfile, dest)
		os.remove(tempfile)
		print( "downloaded and here it is: " + str(dest) )
		#self._load_document("file://%s" % dest)

	def _download_error_cb(self, getter, err, buddy):
		logging.debug("Error getting document from %s (%s): %s" % (buddy.props.nick, buddy.props.ip4_address, err))
		#gobject.idle_add(self._get_document)