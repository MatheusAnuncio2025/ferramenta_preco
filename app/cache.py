# app/cache.py
from cachetools import TTLCache

# Cria um cache que armazena até 128 itens, e cada item expira após 600 segundos (10 minutos)
cache = TTLCache(maxsize=128, ttl=600)
