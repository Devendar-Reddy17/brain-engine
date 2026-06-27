"""Language/framework taggers.

Each module here maps a single language's raw symbol metadata
(annotations/decorators, inheritance, route, naming) to normalized,
cross-language tags such as ``controller``, ``service``, ``repository``,
``config``, ``route``, ``test``. The :mod:`brain.core.parsing.tagging` registry
wires these into ``derive_tags`` so the query layer stays language-agnostic.

Add a new language by creating a ``LANGUAGE``/``derive`` pair here and
registering it in :mod:`brain.core.parsing.tagging`.
"""
