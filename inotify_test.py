import inotify.adapters
import os

notifier = inotify.adapters.Inotify()
notifier.add_watch('/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/asd2/Marxan default scenario/output')

for event in notifier.event_gen():
    if event is not None:
        # print event      # uncomment to see all events generated
        if 'IN_CREATE' in event[1]:
            filename = event[3]
            if filename[:8] == 'output_r':
                print "file '{0}' created in '{1}'".format(event[3], event[2])
            #  os.system("your_python_script_here.py")