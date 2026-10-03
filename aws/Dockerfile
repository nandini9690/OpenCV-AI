# Lambda container image (OpenCV is too big for a zip package)
FROM public.ecr.aws/lambda/python:3.12
RUN dnf install -y mesa-libGL && dnf clean all
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
COPY pipeline/ ${LAMBDA_TASK_ROOT}/pipeline/
COPY agent/    ${LAMBDA_TASK_ROOT}/agent/
COPY aws/lambda_handler.py ${LAMBDA_TASK_ROOT}/
CMD ["lambda_handler.handler"]
