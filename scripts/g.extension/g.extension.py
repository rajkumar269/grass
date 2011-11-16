#!/usr/bin/env python

############################################################################
#
# MODULE:       g.extension
# AUTHOR(S):   	Markus Neteler
#               Pythonized by Martin Landa
# PURPOSE:      Tool to download and install extensions from GRASS Addons SVN into 
#               local GRASS installation
# COPYRIGHT:    (C) 2009-2011 by Markus Neteler, and the GRASS Development Team
#
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
# TODO: add sudo support where needed (i.e. check first permission to write into
#       $GISBASE directory)
#############################################################################

#%module
#% label: Tool to maintain the extensions in local GRASS installation.
#% description: Downloads, installs extensions from GRASS Addons SVN repository into local GRASS installation or removes installed extensions.
#% keywords: general
#% keywords: installation
#% keywords: extensions
#%end

#%option
#% key: extension
#% type: string
#% key_desc: name
#% description: Name of extension to install/remove
#% required: yes
#%end
#%option
#% key: operation
#% type: string
#% description: Operation to be performed
#% required: yes
#% options: add,remove
#% answer: add
#%end
#%option
#% key: svnurl
#% type: string
#% key_desc: url
#% description: SVN Addons repository URL
#% required: yes
#% answer: http://svn.osgeo.org/grass/grass-addons/grass7
#%end
#%option
#% key: prefix
#% type: string
#% key_desc: path
#% description: Prefix where to install extension (ignored when flag -s is given)
#% answer: $GRASS_ADDON_PATH
#% required: no
#%end

#%flag
#% key: l
#% description: List available modules in the GRASS Addons SVN repository
#% guisection: Print
#% suppress_required: yes
#%end
#%flag
#% key: c
#% description: List available modules in the GRASS Addons SVN repository including module description
#% guisection: Print
#% suppress_required: yes
#%end
#%flag
#% key: g
#% description: List available modules in the GRASS Addons SVN repository (shell script style)
#% guisection: Print
#% suppress_required: yes
#%end
#%flag
#% key: s
#% description: Install system-wide (may need system administrator rights)
#%end
#%flag
#% key: d
#% description: Download source code and exit
#%end
#%flag
#% key: i
#% description: Don't install new extension, just compile it
#%end

import os
import sys
import re
import atexit
import shutil
import glob

from urllib2 import urlopen, HTTPError

try:
    import xml.etree.ElementTree as etree
except ImportError:
    import elementtree.ElementTree as etree # Python <= 2.4

from grass.script import core as grass

# temp dir
remove_tmpdir = True

def check():
    for prog in ('svn', 'make', 'gcc'):
        if not grass.find_program(prog, ['--help']):
            grass.fatal(_("'%s' required. Please install '%s' first.") % (prog, prog))
    
def expand_module_class_name(c):
    name = { 'd'   : 'display',
             'db'  : 'database',
             'g'   : 'general',
             'i'   : 'imagery',
             'm'   : 'misc',
             'ps'  : 'postscript',
             'p'   : 'paint',
             'r'   : 'raster',
             'r3'  : 'raster3d',
             's'   : 'sites',
             'v'   : 'vector',
             'gui' : 'gui/wxpython' }
    
    if name.has_key(c):
        return name[c]
    
    return c

def list_available_modules():
    mlist = list()

    # try to download XML metadata file first
    url = "http://grass.osgeo.org/addons/grass%s.xml" % grass.version()['version'].split('.')[0]
    try:
        f = urlopen(url)
        tree = etree.fromstring(f.read())
        for mnode in tree.findall('task'):
            name = mnode.get('name')
            if flags['c'] or flags['g']:
                desc = mnode.find('description').text
                if not desc:
                    desc = ''
                keyw = mnode.find('keywords').text
                if not keyw:
                    keyw = ''
            
            if flags['g']:
                print 'name=' + name
                print 'description=' + desc
                print 'keywords=' + keyw
            elif flags['c']:
                print name + ' - ' + desc
            else:
                print name
    except HTTPError:
        return list_available_modules_svn()
    
    return mlist

def list_available_modules_svn():
    mlist = list()
    grass.message(_('Fetching list of modules from GRASS-Addons SVN (be patient)...'))
    pattern = re.compile(r'(<li><a href=".+">)(.+)(</a></li>)', re.IGNORECASE)
    i = 0
    prefix = ['d', 'db', 'g', 'i', 'm', 'ps',
              'p', 'r', 'r3', 's', 'v']
    nprefix = len(prefix)
    for d in prefix:
        if flags['g']:
            grass.percent(i, nprefix, 1)
            i += 1
        
        modclass = expand_module_class_name(d)
        grass.verbose(_("Checking for '%s' modules...") % modclass)
        
        url = '%s/%s' % (options['svnurl'], modclass)
        grass.debug("url = %s" % url, debug = 2)
        try:
            f = urlopen(url)
        except HTTPError:
            grass.debug(_("Unable to fetch '%s'") % url, debug = 1)
            continue
        
        for line in f.readlines():
            # list modules
            sline = pattern.search(line)
            if not sline:
                continue
            name = sline.group(2).rstrip('/')
            if name.split('.', 1)[0] == d:
                print_module_desc(name, url)
                mlist.append(name)
    
    mlist += list_wxgui_extensions()
    
    if flags['g']:
        grass.percent(1, 1, 1)
    
    return mlist

def list_wxgui_extensions(print_module = True):
    mlist = list()
    grass.debug('Fetching list of wxGUI extensions from GRASS-Addons SVN (be patient)...')
    pattern = re.compile(r'(<li><a href=".+">)(.+)(</a></li>)', re.IGNORECASE)
    grass.verbose(_("Checking for '%s' modules...") % 'gui/wxpython')
    
    url = '%s/%s' % (options['svnurl'], 'gui/wxpython')
    grass.debug("url = %s" % url, debug = 2)
    f = urlopen(url)
    if not f:
        grass.warning(_("Unable to fetch '%s'") % url)
        return
        
    for line in f.readlines():
        # list modules
        sline = pattern.search(line)
        if not sline:
            continue
        name = sline.group(2).rstrip('/')
        if name not in ('..', 'Makefile'):
            if print_module:
                print_module_desc(name, url)
            mlist.append(name)
    
    return mlist

def print_module_desc(name, url):
    if not flags['c'] and not flags['g']:
        print name
        return
    
    if flags['g']:
        print 'name=' + name
    
    # check main.c first
    desc = get_module_desc(url + '/' + name + '/' + name)
    if not desc:
        desc = get_module_desc(url + '/' + name + '/main.c', script = False)
    if not desc:
        if not flags['g']:
            print name + ' - '
            return
    
    if flags['g']:
        print 'description=' + desc.get('description', '')
        print 'keywords=' + ','.join(desc.get('keywords', list()))
    else:
        print name + ' - ' + desc.get('description', '')
    
def get_module_desc(url, script = True):
    grass.debug('url=%s' % url)
    try:
        f = urlopen(url)
    except HTTPError:
        return {}
    
    if script:
        ret = get_module_script(f)
    else:
        ret = get_module_main(f)
        
    return ret

def get_module_main(f):
    if not f:
        return dict()
    
    ret = { 'keyword' : list() }
    
    pattern = re.compile(r'(module.*->)(.+)(=)(.*)', re.IGNORECASE)
    keyword = re.compile(r'(G_add_keyword\()(.+)(\);)', re.IGNORECASE)
    
    key   = ''
    value = ''
    for line in f.readlines():
        line = line.strip()
        find = pattern.search(line)
        if find:
            key = find.group(2).strip()
            line = find.group(4).strip()
        else:
            find = keyword.search(line)
            if find:
                ret['keyword'].append(find.group(2).replace('"', '').replace('_(', '').replace(')', ''))
        if key:
            value += line
            if line[-2:] == ');':
                value = value.replace('"', '').replace('_(', '').replace(');', '')
                if key == 'keywords':
                    ret[key] = map(lambda x: x.strip(), value.split(','))
                else:
                    ret[key] = value
                
                key = value = ''
    
    return ret

def get_module_script(f):
    ret = dict()
    if not f:
        return ret
    
    begin = re.compile(r'#%.*module', re.IGNORECASE)
    end   = re.compile(r'#%.*end', re.IGNORECASE)
    mline = None
    for line in f.readlines():
        if not mline:
            mline = begin.search(line)
        if mline:
            if end.search(line):
                break
            try:
                key, value = line.split(':', 1)
                key = key.replace('#%', '').strip()
                value = value.strip()
                if key == 'keywords':
                    ret[key] = map(lambda x: x.strip(), value.split(','))
                else:
                    ret[key] = value
            except ValueError:
                pass
    
    return ret

def cleanup():
    if remove_tmpdir:
        grass.try_rmdir(tmpdir)
    else:
        grass.message(_("Path to the source code:"))
        sys.stderr.write('%s\n' % os.path.join(tmpdir, options['extension']))
                        
def install_extension_win():
    ### TODO: do not use hardcoded url
    version = grass.version()['version'].split('.')
    url = "http://wingrass.fsv.cvut.cz/grass%s%s/addons" % (version[0], version[1])
    success = False
    grass.message(_("Downloading precompiled GRASS Addons <%s>...") % options['extension'])
    for comp, ext in [(('bin', ), 'exe'),
                      (('docs', 'html'), 'html'),
                      (('man', 'man1'), None),
                      (('scripts', ), 'py')]:
        name = options['extension']
        if ext:
            name += '.' + ext
        try:
            f = urlopen(url + '/' + '/'.join(comp) + '/' + name)
            fo = open(os.path.join(options['prefix'], os.path.sep.join(comp), name), 'wb')
            fo.write(f.read())
            fo.close()
            if comp[0] in ('bin', 'scripts'):
                success = True
        except HTTPError:
            pass

    if not success:
        grass.fatal(_("GRASS Addons <%s> not found") % options['extension'])
    
def install_extension():
    gisbase = os.getenv('GISBASE')
    if not gisbase:
        grass.fatal(_('$GISBASE not defined'))
    
    if grass.find_program(options['extension'], ['--help']):
        grass.warning(_("Extension <%s> already installed. Will be updated...") % options['extension'])
    
    gui_list = list_wxgui_extensions(print_module = False)

    if options['extension'] not in gui_list:
        classchar = options['extension'].split('.', 1)[0]
        moduleclass = expand_module_class_name(classchar)
        url = options['svnurl'] + '/' + moduleclass + '/' + options['extension']
    else:
        url = options['svnurl'] + '/gui/wxpython/' + options['extension']
        if not flags['s']:
            grass.fatal(_("Installation of wxGUI extension requires -%s flag.") % 's')
        
    grass.message(_("Fetching '%s' from GRASS-Addons SVN (be patient)...") % options['extension'])
    
    os.chdir(tmpdir)
    if grass.verbosity() == 0:
        outdev = open(os.devnull, 'w')
    else:
        outdev = sys.stdout
    
    if grass.call(['svn', 'checkout',
                   url], stdout = outdev) != 0:
        grass.fatal(_("GRASS Addons <%s> not found") % options['extension'])
    
    dirs = { 'bin' : os.path.join(tmpdir, options['extension'], 'bin'),
             'docs' : os.path.join(tmpdir, options['extension'], 'docs'),
             'html' : os.path.join(tmpdir, options['extension'], 'docs', 'html'),
             'man' : os.path.join(tmpdir, options['extension'], 'man'),
             'man1' : os.path.join(tmpdir, options['extension'], 'man', 'man1'),
             'scripts' : os.path.join(tmpdir, options['extension'], 'scripts'),
             'etc' : os.path.join(tmpdir, options['extension'], 'etc'),
             }
    
    makeCmd = ['make',
               'MODULE_TOPDIR=%s' % gisbase.replace(' ', '\ '),
               'BIN=%s' % dirs['bin'],
               'HTMLDIR=%s' % dirs['html'],
               'MANDIR=%s' % dirs['man1'],
               'SCRIPTDIR=%s' % dirs['scripts'],
               'ETC=%s' % os.path.join(dirs['etc'],options['extension'])
               ]
    
    installCmd = ['make',
                  'MODULE_TOPDIR=%s' % gisbase,
                  'ARCH_DISTDIR=%s' % os.path.join(tmpdir, options['extension']),
                  'INST_DIR=%s' % options['prefix'],
                  'install'
                  ]
    
    if flags['d']:
        grass.message(_("To compile run:"))
        sys.stderr.write(' '.join(makeCmd) + '\n')
        grass.message(_("To install run:\n\n"))
        sys.stderr.write(' '.join(installCmd) + '\n')
        return
    
    os.chdir(os.path.join(tmpdir, options['extension']))
    
    grass.message(_("Compiling '%s'...") % options['extension'])    
    if options['extension'] not in gui_list:
        ret = grass.call(makeCmd,
                         stdout = outdev)
    else:
        ret = grass.call(['make',
                          'MODULE_TOPDIR=%s' % gisbase.replace(' ', '\ ')],
                         stdout = outdev)
    
    if ret != 0:
        grass.fatal(_('Compilation failed, sorry. Please check above error messages.'))

    if flags['i'] or options['extension'] in gui_list:
        return
    
    grass.message(_("Installing '%s'...") % options['extension'])
    
    ret = grass.call(installCmd,
                     stdout = outdev)
    
    if ret != 0:
        grass.warning(_('Installation failed, sorry. Please check above error messages.'))
    else:
        grass.message(_("Installation of '%s' successfully finished.") % options['extension'])
    
    # manual page: fix href
    if os.getenv('GRASS_ADDON_PATH'):
        html_man = os.path.join(os.getenv('GRASS_ADDON_PATH'), 'docs', 'html', options['extension'] + '.html')
        if os.path.exists(html_man):
            fd = open(html_man)
            html_str = '\n'.join(fd.readlines())
            fd.close()
            for rep in ('grassdocs.css', 'grass_logo.png'):
                patt = re.compile(rep, re.IGNORECASE)
                html_str = patt.sub(os.path.join(gisbase, 'docs', 'html', rep),
                                    html_str)
                
            patt = re.compile(r'(<a href=")(d|db|g|i|m|p|ps|r|r3|s|v|wxGUI)(\.)(.+)(.html">)', re.IGNORECASE)
            while True:
                m = patt.search(html_str)
                if not m:
                    break
                html_str = patt.sub(m.group(1) + os.path.join(gisbase, 'docs', 'html',
                                                              m.group(2) + m.group(3) + m.group(4)) + m.group(5),
                                    html_str, count = 1)
            fd = open(html_man, "w")
            fd.write(html_str)
            fd.close()
    
    if not os.environ.has_key('GRASS_ADDON_PATH') or \
            not os.environ['GRASS_ADDON_PATH']:
        grass.warning(_('This add-on module will not function until you set the '
                        'GRASS_ADDON_PATH environment variable (see "g.manual variables")'))

def remove_extension():
    # try to download XML metadata file first
    url = "http://grass.osgeo.org/addons/grass%s.xml" % grass.version()['version'].split('.')[0]
    name = options['extension']
    try:
        f = urlopen(url)
        tree = etree.fromstring(f.read())
        flist = []
        for task in tree.findall('task'):
            if name == task.get('name', default = '') and \
                    task.find('binary') is not None:
                for f in task.find('binary').findall('file'):
                    fname = f.text
                    if fname:
                        fpath = fname.split('/')
                        if sys.platform == 'win32':
                            if fpath[0] == 'bin':
                                fpath[-1] += '.exe'
                            if fpath[0] == 'scripts':
                                fpath[-1] += '.py'
                        
                        flist.append(fpath)
        if flist:
            removed = False
            err = list()
            for f in flist:
                fpath = os.path.join(options['prefix'], os.path.sep.join(f))
                try:
                    os.remove(fpath)
                    removed = True
                except OSError:
                    err.append((_("Unable to remove file '%s'") % fpath))
            if not removed:
                grass.fatal(_("Extension <%s> not found") % options['extension'])
            
            if err:
                for e in err:
                    grass.error(e)
        else:
            remove_extension_std()
    except HTTPError:
        remove_extension_std()

    grass.message(_("Extension <%s> successfully uninstalled.") % options['extension'])
    
def remove_extension_std():
    # is module available?
    if not os.path.exists(os.path.join(options['prefix'], 'bin', options['extension'])):
        grass.fatal(_("Extension <%s> not found") % options['extension'])
    
    for file in [os.path.join(options['prefix'], 'bin', options['extension']),
                 os.path.join(options['prefix'], 'scripts', options['extension']),
                 os.path.join(options['prefix'], 'docs', 'html', options['extension'] + '.html')]:
        if os.path.isfile(file):
            os.remove(file)
    
def create_dir(path):
    if os.path.isdir(path):
        return
    
    try:
        os.makedirs(path)
    except OSError, e:
        grass.fatal(_("Unable to create '%s': %s") % (path, e))
    
    grass.debug("'%s' created" % path)

def check_style_files(fil):
    #check the links to grassdocs.css/grass_logo.png to a correct manual page of addons
    dist_file = os.path.join(os.getenv('GISBASE'),'docs','html',fil)
    addons_file = os.path.join(options['prefix'],'docs','html',fil)
    #check if file already exists in the grass addons docs html path
    if os.path.isfile(addons_file):
	return
    #otherwise copy the file from $GISBASE/docs/html, it doesn't use link 
    #because os.symlink it work only in Linux
    else:
	try:
	    shutil.copyfile(dist_file,addons_file)
	except OSError, e:
	    grass.fatal(_("Unable to create '%s': %s") % (addons_file, e))

def check_dirs():
    create_dir(os.path.join(options['prefix'], 'bin'))
    create_dir(os.path.join(options['prefix'], 'docs', 'html'))
    check_style_files('grass_logo.png')
    check_style_files('grassdocs.css')    
    create_dir(os.path.join(options['prefix'], 'man', 'man1'))
    create_dir(os.path.join(options['prefix'], 'scripts'))

def main():
    # check dependecies
    if sys.platform != "win32":
        check()
    
    # list available modules
    if flags['l'] or flags['c'] or flags['g']:
        list_available_modules()
        return 0
    else:
        if not options['extension']:
            grass.fatal(_('You need to define an extension name or use -l'))
    
    # define path
    if flags['s']:
        options['prefix'] = os.environ['GISBASE']
    if options['prefix'] == '$GRASS_ADDON_PATH':
        if not os.environ.has_key('GRASS_ADDON_PATH') or \
                not os.environ['GRASS_ADDON_PATH']:
            major_version = int(grass.version()['version'].split('.', 1)[0])
            grass.warning(_("GRASS_ADDON_PATH is not defined, "
                            "installing to ~/.grass%d/addons/") % major_version)
            options['prefix'] = os.path.join(os.environ['HOME'], '.grass%d' % major_version, 'addons')
        else:
            path_list = os.environ['GRASS_ADDON_PATH'].split(os.pathsep)
            if len(path_list) < 1:
                grass.fatal(_("Invalid GRASS_ADDON_PATH value - '%s'") % os.environ['GRASS_ADDON_PATH'])
            if len(path_list) > 1:
                grass.warning(_("GRASS_ADDON_PATH has more items, using first defined - '%s'") % path_list[0])
            options['prefix'] = path_list[0]
    
    # check dirs
    check_dirs()
    
    if flags['d']:
        if options['operation'] != 'add':
            grass.warning(_("Flag 'd' is relevant only to 'operation=add'. Ignoring this flag."))
        else:
            global remove_tmpdir
            remove_tmpdir = False
    
    if options['operation'] == 'add':
        if sys.platform == "win32":
            install_extension_win()
        else:
            install_extension()
    else: # remove
        remove_extension()
    
    return 0

if __name__ == "__main__":
    options, flags = grass.parser()
    global tmpdir
    tmpdir = grass.tempdir()
    atexit.register(cleanup)
    sys.exit(main())
