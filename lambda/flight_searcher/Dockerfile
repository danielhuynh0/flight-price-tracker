FROM public.ecr.aws/lambda/python:3.11

RUN yum install -y gcc libcurl-devel openssl-devel && yum clean all

WORKDIR ${LAMBDA_TASK_ROOT}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py sqs_client.py flight_scraper.py handler.py ./

CMD ["handler.lambda_handler"]
