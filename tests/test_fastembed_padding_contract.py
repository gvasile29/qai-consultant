"""Dependency-contract guard for issue #105: the pinned fastembed must tolerate
a model snapshot whose tokenizer.json uses fixed padding shorter than its
truncation limit.

Qdrant/all-MiniLM-L6-v2-onnx shipped exactly that between 2026-09-27 and
2026-09-30 (revision 8f518e88: Fixed 128 padding, 256 truncation). fastembed
0.8.0 kept the fixed padding, so any batch mixing chunks under and over 128
tokens came back ragged and numpy raised "inhomogeneous shape" — breaking
every KB-backed MCP tool for anyone whose fastembed_cache held that snapshot.
fastembed 0.8.1 (qdrant/fastembed#703) switches such tokenizers to
batch-longest padding. A tiny synthetic tokenizer reproduces the snapshot's
shape without a model download.
"""
import json

import numpy as np
import pytest

tokenizers = pytest.importorskip("tokenizers")
preprocessor_utils = pytest.importorskip("fastembed.common.preprocessor_utils")

_VOCAB = {"[PAD]": 0, "[UNK]": 1, "short": 2, "word": 3}
_FIXED_PAD = 4
_TRUNCATION = 16


def _write_fixed_padding_model(model_dir):
    tok = tokenizers.Tokenizer(tokenizers.models.WordLevel(_VOCAB, unk_token="[UNK]"))
    tok.pre_tokenizer = tokenizers.pre_tokenizers.Whitespace()
    tok.enable_padding(length=_FIXED_PAD, pad_id=0, pad_token="[PAD]")
    tok.enable_truncation(max_length=_TRUNCATION)
    tok.save(str(model_dir / "tokenizer.json"))
    (model_dir / "tokenizer_config.json").write_text(
        json.dumps({"model_max_length": _TRUNCATION, "pad_token": "[PAD]"}), encoding="utf-8"
    )
    (model_dir / "config.json").write_text(json.dumps({"pad_token_id": 0}), encoding="utf-8")
    (model_dir / "special_tokens_map.json").write_text(
        json.dumps({"pad_token": "[PAD]", "unk_token": "[UNK]"}), encoding="utf-8"
    )


def test_mixed_length_batch_is_homogeneous_with_fixed_padding_below_truncation(tmp_path):
    _write_fixed_padding_model(tmp_path)
    tokenizer, _ = preprocessor_utils.load_tokenizer(tmp_path)

    encoded = tokenizer.encode_batch(["short", "word " * 10])

    lengths = [len(e.ids) for e in encoded]
    assert len(set(lengths)) == 1, f"ragged batch {lengths}: fastembed kept fixed padding (issue #105)"
    # The same np.array call fastembed's onnx_embed makes — raised ValueError before the fix.
    assert np.array([e.ids for e in encoded]).shape == (2, lengths[0])
