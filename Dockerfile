FROM python:3.9-alpine
RUN pip install dd2482-course-automation

CMD ["ddca", "--deadline=", $deadline, "--event=", $event_path, "--secret=", $secret]
