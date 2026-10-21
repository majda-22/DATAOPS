FROM eclipse-temurin:17-jre-jammy AS java-runtime

FROM apache/airflow:3.3.2-python3.11

COPY --from=java-runtime /opt/java/openjdk /opt/java/openjdk

ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="/opt/java/openjdk/bin:${PATH}"

USER airflow

COPY --chown=airflow:root pyproject.toml /opt/dataops/pyproject.toml
COPY --chown=airflow:root dataops/ /opt/dataops/dataops/
COPY --chown=airflow:root configs/spark/ivysettings.xml /opt/dataops/configs/spark/ivysettings.xml

RUN pip install --no-cache-dir \
    "apache-airflow==3.3.2" \
    "/opt/dataops[db,storage,spark]" \
    && pip check

RUN java -version