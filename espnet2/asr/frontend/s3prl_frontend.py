from argparse import Namespace
import copy
import logging
from typing import Optional
from typing import Tuple
from typing import Union

import humanfriendly
import torch
import torch.nn as nn
from typeguard import check_argument_types

from espnet.nets.pytorch_backend.frontends.frontend import Frontend
from espnet.nets.pytorch_backend.nets_utils import pad_list
from espnet2.asr.frontend.abs_frontend import AbsFrontend
from espnet2.utils.get_default_kwargs import get_default_kwargs


def base_s3prl_setup(args):
    args.upstream_feature_selection = getattr(args, "upstream_feature_selection", None)
    args.upstream_model_config = getattr(args, "upstream_model_config", None)
    args.upstream_refresh = getattr(args, "upstream_refresh", False)
    args.upstream_ckpt = getattr(args, "upstream_ckpt", None)
    args.init_ckpt = getattr(args, "init_ckpt", None)
    args.verbose = getattr(args, "verbose", False)

    return args


class S3prlFrontend(AbsFrontend):
    """Speech Pretrained Representation frontend structure for ASR."""

    def __init__(
        self,
        fs: Union[int, str] = 16000,
        frontend_conf: Optional[dict] = get_default_kwargs(Frontend),
        download_dir: str = None,
    ):
        assert check_argument_types()
        super().__init__()
        if isinstance(fs, str):
            fs = humanfriendly.parse_size(fs)

        if download_dir is not None:
            torch.hub.set_dir(download_dir)

        self.upstream = self._get_upstream(frontend_conf)
        self.pretrained_params = copy.deepcopy(self.upstream.state_dict())
        self.upstream_trainable = getattr(self.args, "upstream_trainable", False)
        self.output_dim = self.upstream.get_output_dim()

    def _get_upstream(self, frontend_conf):
        # S3PRL upstream model
        s3prl_args = base_s3prl_setup(
            Namespace(**frontend_conf, device="cpu"),
        )

        assert getattr(self, "args", None) is None
        assert getattr(self, "init_ckpt", None) is None
        self.args = s3prl_args
        self.init_ckpt = {}

        from downstream.runner import Runner  # S3PRL Runner

        return Runner._get_upstream(self)

    def output_size(self) -> int:
        return self.output_dim

    def forward(
        self, input: torch.Tensor, input_lengths: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        wavs = [wav[: input_lengths[i]] for i, wav in enumerate(input)]
        if self.upstream_trainable:
            feats = self.upstream(wavs)
        else:
            with torch.no_grad():
                feats = self.upstream(wavs)
        input_feats = pad_list(feats, 0.0)
        feats_lens = torch.tensor([f.shape[0] for f in feats], dtype=torch.long)

        # Saving CUDA Memory
        del feats

        return input_feats, feats_lens

    def reload_pretrained_parameters(self):
        self.upstream.load_state_dict(self.pretrained_params)
        logging.info("Pretrained S3PRL frontend model parameters reloaded!")
