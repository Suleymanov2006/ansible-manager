import os
import signal
import traceback
from time import sleep

from multiprocessing import Process
from subprocess import PIPE, Popen

from core import consts
from core import models


class TaskManager:
    def run(self):
        """ Tasks monitoring and check status"""
        while True:
            self.check_in_progress()
            self.start_wait_tasks()
            sleep(1)

    def check_in_progress(self):
        tasks = models.Task.objects.filter(status=consts.IN_PROGRESS, pid__isnull=False)
        not_run_tasks = []
        for task in tasks:
            if not task.pid:
                models.TaskLog.objects.create(
                    task=task,
                    status=consts.FAIL,
                    message='Error "pid is None"',
                )
                continue

            if not self._is_process_run(task.pid):
                not_run_tasks.append(task)

        for task in not_run_tasks:
            task.status = consts.FAIL
            task.save()

            models.TaskLog.objects.create(
                task=task,
                status=consts.FAIL,
                message='Task with pid %s is not running' % task.pid
            )

    def start_wait_tasks(self):
        tasks = models.Task.objects.filter(status=consts.WAIT)
        for task in tasks:
            self.run_task_process(task)

    @staticmethod
    def run_task(task_id):
        from django.db import connection
        connection.connection.close()
        connection.connection = None

        task = models.Task.objects.get(id=task_id)

        task.logs.create(
            status=consts.IN_PROGRESS,
            message='Run with pid %s in new process' % task.pid,
        )

        command = task.get_command(splited=True)
        inventory_file_path = command[2]
        task.logs.create(
            status=consts.IN_PROGRESS,
            message='Command: %s' % ' '.join(command),
        )

        try:
            proc = Popen(command, stdout=PIPE, stderr=PIPE)
            while proc.poll() is None:
                output = proc.stdout.readline()

                if output:
                    models.TaskLog.objects.create(
                        task=task,
                        status=consts.IN_PROGRESS,
                        output=output
                    )

            code = proc.returncode
            if code == 0:
                output = proc.stdout.readline()
                if output:
                    models.TaskLog.objects.create(
                        task=task,
                        status=consts.IN_PROGRESS,
                        output=output
                    )
                task.status = consts.COMPLETED
                task.save()
                models.TaskLog.objects.create(
                    task=task,
                    status=consts.COMPLETED,
                    message='Task complete'
                )
            else:
                task.status = consts.FAIL
                task.save()
                _, err = proc.communicate()
                models.TaskLog.objects.create(
                    task=task,
                    status=consts.FAIL,
                    output=err,
                    message='Failed with status code %s' % code
                )

        except Exception as e:
            task.status = consts.FAIL
            task.save()
            traceback_message = traceback.format_exc()
            models.TaskLog.objects.create(
                task=task,
                output=traceback_message,
                message='Progress error "%s"' % e,
                status=consts.FAIL
            )
        finally:
            os.remove(inventory_file_path)
            if os.path.exists("/proc/%s" % task.pid):
                os.kill(task.pid, signal.SIGTERM)

    @staticmethod
    def stop_task(task):
        assert task.status in consts.RUN_STATUSES

        if task.status == consts.IN_PROGRESS and task.pid:
            try:
                os.kill(task.pid, signal.SIGTERM)
            except Exception as e:
                traceback_message = traceback.format_exc()
                models.TaskLog.objects.create(
                    task=task,
                    output=traceback_message,
                    messgae='Stop error "%s"' % e,
                    status=consts.FAIL
                )

        task.status = consts.STOPPED
        task.save()
        models.TaskLog.objects.create(
            task=task,
            status=consts.STOPPED,
            message='Task stopped'
        )

    def run_task_process(self, task):
        proc = Process(target=self.run_task, args=(task.id,))
        proc.start()
        pid = proc.pid

        from django.db import connection
        connection.connection.close()
        connection.connection = None

        models.TaskLog.objects.create(
            task=task,
            status=consts.IN_PROGRESS,
            message='Start task with pid %s' % pid,
        )

        task.pid = pid
        task.status = consts.IN_PROGRESS
        task.save()

    @staticmethod
    def _is_process_run(pid):
        return os.path.exists("/proc/%s" % pid)

