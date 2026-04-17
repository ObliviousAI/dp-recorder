FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pytest \
    numpy \
    pandas \
    scipy \
    scikit-learn \
    tqdm \
    matplotlib \
    seaborn \
    graphviz \
    opendp==0.14.1 \
    dp-accounting \
    networkx \
    disjoint-set \
    jax \
    jaxlib \
    chex \
    optax \
    attrs \
    pgmpy \
    pydantic \
    requests \
    loguru \
    optuna \
    Pillow \
    cloudpickle \
    lifelines \
    opacus \
    tenacity \
    ipython \
    xgboost

RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

WORKDIR /workspace
