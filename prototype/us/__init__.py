"""TradePilot US Market module — isolated from the India stack.

Separate cache namespace, separate universe, separate history. See data_us.py
for why: the India engines' shared cache has been a poisoning vector twice.
"""
