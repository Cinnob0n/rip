#!/usr/bin/python

import cgitb; cgitb.enable() # for debugging
import cgi # for getting query keys/values

from os       import listdir, path, walk, utime, stat, environ, remove, chdir
from json     import dumps
from random   import randrange
from datetime import datetime
from time     import time
from urllib   import quote, unquote
from shutil   import rmtree
sep = '/'
##################
# MAIN

def main(): # Prints JSON response to query
	keys = get_keys()
	
	if path.exists('rips'):
		chdir('rips')

	# Gets keys or defaults
	start   = int(keys.get('start',   0))   # Starting index (album/images)
	count   = int(keys.get('count',   20))  # Number of images/thumbs to retrieve
	preview = int(keys.get('preview', 10))  # Number of images to retrieve
	after   =     keys.get('after',   '')   # Next album to retrieve
	blacklist =   keys.get('blacklist', '') # Album to blacklist

	# Get from list of all albums
	if  'view_all' in keys: get_all_albums(count, preview, after)

	# Get images from one album
	elif 'view'          in keys: get_album(keys['view'].replace(' ', '%20'), start, count)
	# Get URLs for an album
	elif 'urls'          in keys: get_urls_for_album(keys['urls'])
	# Get albums ripped by a user
	elif 'user'          in keys: get_albums_for_user(keys['user'], count, preview, after)
	# Report an album
	elif 'report'        in keys: report_album(keys['report'], reason=keys.get('reason', ''))
	# Get from list of reported album
	elif 'get_report'    in keys: get_reported_albums(count, preview, after)
	# Remove all reports or an album
	elif 'clear_reports' in keys: clear_reports(keys['clear_reports'])
	# Delete an album, add to blacklist
	elif 'delete'        in keys: delete_album(keys['delete'], blacklist)
	# Delete all albums from a user
	elif 'delete_user'   in keys: delete_albums_by_user(keys['delete_user'], blacklist)
	# Permanently ban a user
	elif 'ban_user'      in keys: ban_user(keys['ban_user'], reason=keys.get('reason', ''))

	# Unexpected key(s)
	else: print_error('unsupported method(s)')


###################
# ALBUMS

def get_all_albums(count, preview_size, after):
	found_after = False # User-specified 'after' was found in list of directories
	# Get directories and timestamps
	thedirs = []
	for f in listdir('.'):
		if not path.isdir(f): continue
		if not path.exists('%s.zip' % f): continue
		if not found_after and after != '' and f == after: found_after = True
		thedirs.append( (f, path.getmtime(f) ) )
	# Sort by most recent
	thedirs = sorted(thedirs, key=lambda k: k[1], reverse=True)
	
	# Strip out timestamp
	for i in xrange(0, len(thedirs)):
		thedirs[i] = thedirs[i][0]
	
	# Filter results
	filter_albums(thedirs, count, preview_size, after, found_after)


def get_albums_for_user(user, count, preview_size, after):
	found_after = False # User-specified 'after' was found in list of directories
	# Get directories and timestamps
	thedirs = []
	for f in listdir('.'):
		if not path.isdir(f): continue
		if not path.exists('%s.zip' % f): continue
		if not found_after and after != '' and f == after: found_after = True
		iptxt = path.join(f, 'ip.txt')
		if not path.exists(iptxt): continue
		fil = open(iptxt, 'r')
		ip = fil.read().strip()
		fil.close()
		if user == 'me' and ip != environ['REMOTE_ADDR']: continue
		if user != 'me' and ip != user: continue
		thedirs.append( (f, path.getmtime(f) ) )
	
	# Sort by most recent
	thedirs = sorted(thedirs, key=lambda k: k[1], reverse=True)
	
	# Strip out timestamp
	for i in xrange(0, len(thedirs)):
		thedirs[i] = thedirs[i][0]
	
	# Filter results
	filter_albums(thedirs, count, preview_size, after, found_after)
	

def get_reported_albums(count, preview_size, after):
	if not is_admin():
		print_error('')
		return
	
	found_after = False # User-specified 'after' was found in list of directories
	# Get reported directories & number of reports
	thedirs = []
	for f in listdir('.'):
		if not path.isdir(f): continue
		reportstxt = path.join(f, 'reports.txt')
		if not path.exists(reportstxt): continue
		if not found_after and after != '' and f == after: found_after = True
		fil = open(reportstxt, 'r')
		reports = fil.read().split('\n')
		fil.close()
		thedirs.append( (f, len(reports) ) )
	
	# Sort by most recent
	thedirs = sorted(thedirs, key=lambda k: int(k[1]), reverse=True)
	
	# Strip out timestamp
	for i in xrange(0, len(thedirs)):
		thedirs[i] = thedirs[i][0]
	
	# Filter results
	filter_albums(thedirs, count, preview_size, after, found_after)


def filter_albums(thedirs, count, preview_size, after, found_after):
	dcount = 0 # Number of albums retrieved & returned to user
	dtotal = 0 # Total number of albums
	dindex = 0 # Current index of last_after
	
	admin = is_admin()
	if not found_after: after = '' # Requested 'after' not found, don't look for it
	
	if after == '': 
		hit_after = True
	else:
		hit_after = False
	
	last_after = '' # Last album retrieved
	albums = []
	# Iterate over directories
	for f in thedirs:
		dtotal += 1
		
		# Check if we hit the 'after' specified by request
		if f == after:
			hit_after = True
		
		if not hit_after:
			# Haven't hit 'after' yet, keep iterating
			dindex += 1
			continue
		
		# We hit the number of albums we're supposed to grab
		if (dcount >= count and count != -1):
			last_after = f
			break
		dindex += 1
		
		result = get_images_for_album(f, 0, -1) # Get all images
		images = result['images']
		if len(images) == 0: continue # Don't consider empty albums
		
		dcount += 1 # Increment number of albums retrieved
		
		# Randomly pick 'preview_size' number of thumbnails from the album
		rand = []
		if len(images) <= preview_size:
			rand = xrange(0, len(images))
		else:
			while len(rand) < preview_size:
				i = randrange(len(images) - 1)
				if not i in rand:
					rand.append(i)
			rand.sort()
		preview = []
		for i in rand:
			preview.append( images[i] )
		
		album_result = {
			'album'  : f,
			'images' : preview,
			'total'  : result['total'],
			'time'   : path.getmtime(f)
		}

		# Retrieve number of reports if user is admin
		if admin:
			rtxt = path.join(f, 'reports.txt')
			if path.exists(rtxt):
				fil = open(rtxt, 'r')
				album_result['reports'] = len(fil.read().strip().split('\n'))
				fil.close()
		# Add album to response
		albums.append( album_result )
	
	if dindex == len(thedirs):
		last_after = ''
	
	# Dump response
	print dumps( { 
		'albums' : albums,
		'total'  : len(thedirs),
		'after'  : last_after,
		'index'  : dindex,
		'count'  : dtotal
		} )


##################
# SINGLE ALBUM
def get_images_for_album(album, start, count, thumbs=False):
	if not path.exists(album):
		return {
			'images'  : [],
			'count'   : 0,
			'album'   : '[not found]',
			'archive' : './'
		}
	result = {}
	images = []
	dstart = 0
	dcount = 0
	dtotal = 0
	while album.endswith(sep): album = album[:-1]
	for roots, dirs, files in walk(album):
		if thumbs and not roots.endswith('/thumbs'): continue
		if not thumbs and roots.endswith('/thumbs'): continue
		files.sort()
		for f in files:
			if f.endswith('.txt'): continue
			if dstart >= start and (dcount < count or count == -1):
				image = '%s%s%s' % (roots, sep, f)
				image = image.replace('%', '%25')
				images.append( { 
						'image' : image, 
						'thumb' : get_thumb(image) 
					})
				dcount += 1
			dstart += 1
			dtotal += 1

	result['images']  = images
	result['total']   = dtotal
	result['start']   = start
	result['count']   = dcount
	result['album']   = album.replace('%20', ' ')
	result['archive'] = './%s.zip' % album.replace(' ', '%20').replace('%20', '%2520')
	return result


def get_album(album, start, count):
	result = get_images_for_album(album, start, count)
	if start == 0:
		update_album(album) # Mark album as recently-viewed
	result['url'] = get_url_for_album(album)
	if start == 0 and is_admin():
		result['report_reasons'] = get_report_reasons(album)
		iptxt = path.join(album, 'ip.txt')
		if path.exists(iptxt):
			f = open(iptxt, 'r')
			ip = f.read()
			f.close()
			result['user'] = ip
	print dumps( { 'album' : result } )


# Return external URL for album that was ripped
def get_url_for_album(album):
	logtxt = path.join(album, 'log.txt')
	if not path.exists(logtxt): return ''
	f = open(logtxt, 'r')
	lines = f.read().split('\n')
	f.close()
	if len(lines) == 0: return ''
	url = lines[0]
	if not ' ' in url: return ''
	return url[url.rfind(' ')+1:]


# Return all URLs for an album
def get_urls_for_album(album):
	album = quote(album)
	if not path.exists(album):
		print dumps( { 'urls' : [] } )
		return
	result = []
	for f in listdir(album):
		f = path.join(album, f)
		if f.endswith('.txt'): continue
		if f.endswith('.html'): continue
		if path.isdir(f): continue
		result.append( f )
	result = sorted(result)
	print dumps( { 'urls' : result } )


#############
# REPORT
def report_album(album, reason=""):
	album = quote(album)
	if '..' in album or '/' in album or not path.isdir(album):
		print_error('unable to reported: invalid album specified')
		return
	if not path.exists(album):
		print_error('album does not exist: %s' % album)
		return
	reports = path.join(album, 'reports.txt')
	if path.exists(reports):
		f = open(reports, 'r')
		lines = f.read().split('\n')
		f.close()
		for line in lines:
			if line.startswith(environ['REMOTE_ADDR']):
				print_warning('you (%s) have already reported this album' % environ['REMOTE_ADDR'])
				return
	try:
		f = open(reports, 'a')
		f.write('%s:%s\n' % (environ['REMOTE_ADDR'], reason))
		f.close()
	except Exception, e:
		print_error('unable to report album: %s' % str(e))
		return

	print_ok('this album has been reported. the admins will look into this soon')


def get_report_reasons(album):
	# Sanitization, check if album
	if '..' in album or '/' in album or not path.isdir(album):
		return []
	# No album
	if not path.exists(album):
		return []
	# No reports
	reports = path.join(album, 'reports.txt')
	if not path.exists(reports):
		return []
	f = open(reports, 'r')
	lines = f.read().split('\n')
	f.close()
	reasons = []
	for line in lines:
		if line.strip() == '': continue
		ip = line[:line.find(':')]
		reason = line[line.find(':')+1:]
		reasons.append( {
			'user'   : ip,
			'reason' : reason
		} )
	return reasons

def clear_reports(album):
	if not is_admin():
		print_error('you are not an admin: %s' % environ['REMOTE_ADDR'])
		return
	album = quote(album)
	# Sanitization, check if album
	if '..' in album or '/' in album or not path.isdir(album):
		print_error('album is not valid: %s' % album)
		return
	# No album
	if not path.exists(album):
		print_warning('album not found: %s' % album)
		return
	# No reports
	reports = path.join(album, 'reports.txt')
	if not path.exists(reports):
		print_warning('no reports found: %s' % reports)
		return
	remove(reports)
	print_ok('reports cleared')
	
def delete_album(album, blacklist=''):
	if not is_admin():
		print_error('you are not an admin: %s' % environ['REMOTE_ADDR'])
		return
	album = quote(album)
	# Sanitization, check if album
	if '..' in album or '/' in album or not path.isdir(album):
		print_error('album is not valid: %s' % album)
		return
	# No album
	if not path.exists(album):
		print_warning('album not found: %s' % album)
		return
	
	blacklisted = zipdel = albumdel = False
	# Add URL to blacklist
	url = get_url_for_album(album)
	if blacklist == 'true' and url != '':
		blacklist_url(url)
		blacklisted = True

	# Delete zip
	try:
		remove('%s.zip' % album)
		zipdel = True
	except: pass
	
	# Delete album dir
	try:
		rmtree(album)
		albumdel = True
	except: pass

	# Respond accordingly
	response = ''
	if blacklisted:
		response = ' and album was blacklisted'
	if albumdel and zipdel:
		print_ok('album and zip were both deleted%s' % response)
	elif albumdel:
		print_warning('album was deleted, zip was not found%s' % response)
	elif zipdel:
		print_warning('zip was deleted, album was not found%s' % response)
	else:
		print_error('neither album nor zip were deleted%s' % response)

def delete_albums_by_user(user, blacklist=''):
	if not is_admin():
		print_error('you are not an admin: %s' % environ['REMOTE_ADDR'])
		return
	deleted = []
	for d in listdir('.'):
		if not path.isdir(d): continue
		iptxt = path.join(d, 'ip.txt')
		if not path.exists(iptxt): continue
		f = open(iptxt, 'r')
		ip = f.read().replace('\n', '').strip()
		f.close()
		if ip != user: continue

		blacklisted = delalbum = delzip = False

		# Add URL to blacklist
		url = get_url_for_album(d)
		if blacklist == 'true' and url != '':
			blacklist_url(url)
			blacklisted = True
	
		# Delete zip
		try: 
			remove('%s.zip' % d)
			delzip = True
		except: pass
		# Delete album
		try: 
			rmtree(d)
			delalbum = True
		except: pass

		blresponse = ''
		if blacklisted:
			blresponse = ' + blacklist'
		if delzip and delalbum:
			deleted.append('%s/ and %s.zip%s' % (d, d, blresponse))
		elif delzip:
			deleted.append('%s.zip%s' % (d, blresponse))
		elif delalbum:
			deleted.append('%s/%s' % (d, blresponse))
	print dumps( {
		'deleted' : deleted,
		'user'    : user
	} )

def ban_user(user, reason=""):
	if not is_admin():
		print_error('you (%s) are not an admin' % environ['REMOTE_ADDR'])
		return
	try:
		f = open('../.htaccess', 'r')
		lines = f.read().split('\n')
		f.close()
	except:
		print_error('unable to read from ../.htaccess file -- user not banned.')
		return
	if not 'allow from all' in lines:
		print_error('unable to ban user; cannot find "allow from all" line in htaccess')
		return
	if ' deny from %s' % user in lines:
		print_warning('user is already banned')
		return
	reason = reason.replace('\n', '').replace('\r', '')
	lines.insert(lines.index('allow from all'), '# added by admin %s at %s (reason: %s)' % (environ['REMOTE_ADDR'], int(time()), reason))
	lines.insert(lines.index('allow from all'), ' deny from %s' % user)
	lines.insert(lines.index('allow from all'), '')
	try:
		f = open('../.htaccess', 'w')
		f.write('\n'.join(lines))
		f.close()
	except Exception, e:
		print_error('failed to ban %s: %s' % (user, str(e)))
		return
	print_ok('permanently banned %s' % user)


##################
# HELPER FUNCTIONS

# Print generic messages in JSON format
def print_error  (text): print dumps( { 'error'   : text } )
def print_warning(text): print dumps( { 'warning' : text } )
def print_ok     (text): print dumps( { 'ok'      : text } )

def get_keys(): # Retrieve key/value pairs from query, puts in dict
	form = cgi.FieldStorage()
	keys = {}
	for key in form.keys():
		keys[key] = form[key].value
	return keys

def get_thumb(img): # Get thumbnail based on image, or 'nothumb.png' if not found
	fs = img.split(sep)
	fs.insert(-1, 'thumbs')
	f = sep.join(fs)
	if f.endswith('.mp4'):
		fname = fs.pop(-1).replace('.mp4', '.png')
		fs.append(fname)
		f = sep.join(fs)
		if path.exists(f):
			return f
		else:
			return 'playthumb.png'
	if f.endswith('.html'):
		return 'albumthumb.png'
	if not path.exists(f.replace('%25', '%')):
		return 'nothumb.png'
	return sep.join(fs)


##############
# UPDATE

def update_album(album): # Mark album as recently-viewed
	if path.exists(album):
		update_file_modified(album)
	zipfile = '%s.zip' % album
	if path.exists(zipfile):
		update_file_modified(zipfile)
	
def update_file_modified(f): # Sets system 'modified time' to current time
	st = stat(f)
	atime = int(st.st_atime)
	mtime = int(time())
	try:
		utime(f, (atime, mtime))
	except Exception, e:
		return False
	return True

def is_admin(): # True if user's IP is in the admin list
	if not 'REMOTE_ADDR' in environ: environ['REMOTE_ADDR'] = '127.0.0.1'
	user = environ['REMOTE_ADDR']
	try:
		f = open('../admin_ip.txt', 'r')
		ips = f.read().split('\n')
		f.close()
	except:
		ips = ['127.0.0.1']
	for ip in ips:
		ip = ip.strip()
		if len(ip) < 7: continue
		if ip == user:
			return True
	return False

def blacklist_url(url):
	if not url.startswith('http://') and \
	   not url.startswith('https://'):
		url = 'http://%s' % line
	# Use site's main 'rip.cgi' to get the ripper from the URL
	from sys import path as syspath
	syspath.append('..')
	from rip import get_ripper
	try:
		ripper = get_ripper(url)
		# Get directory name from URL
		to_blacklist = path.basename(ripper.working_dir)
	except Exception, e:
		# Default to just the URL
		to_blacklist = url.replace('http://', '').replace('https://', '')
	# Add to blacklist
	f = open('../url_blacklist.txt', 'a')
	f.write('%s\n' % to_blacklist)
	f.close()

# Entry point. Print leading/trailing characters, execute main()
if __name__ == '__main__':
	print "Content-Type: application/json"
	print ""
	main()
	print "\n"

