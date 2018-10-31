import os

import arcpy


class pyt_log(object):
    """
    A custom logging class to simultaneously write to the console and logfile.
    Will unpack optional arguments to the logfile.
    """
       
    def __init__(self, log_path):
        self.log_path = log_path
    
    def _write_arg(self, arg, path, starting_level=0):
        """Accepts a [path] txt from open(path) and unpacks the data [arg]"""
        level = starting_level
        txtfile = open(path, 'a')
        if level == 0:
            txtfile.write("_"*80)
        if type(arg) == dict:
            txtfile.write("\n"+(level*"\t")+(str(arg))+"\n")
            txtfile.write((level*"\t")+str(type(arg))+"\n")
            for key, value in arg.items():
                txtfile.write((level*"\t\t")+(str(key))+": "+(str(value))+"\n")
                if hasattr(value, '__iter__'):
                    txtfile.write((level*"\t")+"Values:"+"\n")
                    txtfile.close()
                    for val in value:
                        self._write_arg(val, path, starting_level=level+1)
        else:
            txtfile.write("\n"+(level*"\t")+(str(arg))+"\n")
            txtfile.write((level*"\t")+str(type(arg))+"\n")
            if hasattr(arg, '__iter__'): #does not include strings
                txtfile.write((level*"\t")+"Iterables:"+"\n")
                txtfile.close()
                for a in arg:
                    self._write_arg(a, path, starting_level=level+1)

    def _writer(self, msg, path, *args):
        """A writer to write the msg, and unpacked variable"""
        if os.path.exists(path):
            write_type = 'a'
        else:
            write_type = 'w'
        with open(path, write_type) as txtfile:
            txtfile.write("\n"+msg+"\n")
            txtfile.close()
            if args:
                for arg in args:
                    self._write_arg(arg, path)

    def console(self, msg):
        """Print to console only"""
        arcpy.AddMessage(msg)

    def logfile(self, msg, *args):
        """Write to logfile only"""
        path = self.log_path
        self._writer(msg, path, *args)
        
    def log_all(self, msg, *args):
        """Write to all"""
        self.console(msg)
        self.logfile(msg, *args)