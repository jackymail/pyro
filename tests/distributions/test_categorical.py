from __future__ import absolute_import, division, print_function

from unittest import TestCase

import numpy as np
import pytest
import scipy.stats as sp
import torch

import pyro.distributions as dist
from tests.common import assert_equal


class TestCategorical(TestCase):
    """
    Tests methods specific to the Categorical distribution
    """

    def setUp(self):
        n = 1
        self.ps = torch.tensor([0.1, 0.6, 0.3])
        self.batch_ps = torch.tensor([[0.1, 0.6, 0.3], [0.2, 0.4, 0.4]])
        self.n = torch.tensor([n])
        self.test_data = torch.tensor([2])
        self.analytic_mean = n * self.ps
        one = torch.ones(3)
        self.analytic_var = n * torch.mul(self.ps, one.sub(self.ps))

        # Discrete Distribution
        self.d_ps = torch.tensor([[0.2, 0.3, 0.5], [0.1, 0.1, 0.8]])
        self.d_test_data = torch.tensor([[0], [5]])

        self.n_samples = 50000

        self.support_non_vec = torch.tensor([0, 1, 2])
        self.support = torch.tensor([[0, 0], [1, 1], [2, 2]])

    def test_log_prob_sum(self):
        log_px_torch = dist.Categorical(self.ps).log_prob(self.test_data).sum().item()
        log_px_np = float(sp.multinomial.logpmf(np.array([0, 0, 1]), 1, self.ps.detach().cpu().numpy()))
        assert_equal(log_px_torch, log_px_np, prec=1e-4)

    def test_mean_and_var(self):
        torch_samples = [dist.Categorical(self.ps).sample().detach().cpu().numpy()
                         for _ in range(self.n_samples)]
        _, counts = np.unique(torch_samples, return_counts=True)
        computed_mean = float(counts[0]) / self.n_samples
        assert_equal(computed_mean, self.analytic_mean.detach().cpu().numpy()[0], prec=0.05)

    def test_support_non_vectorized(self):
        s = dist.Categorical(self.d_ps[0].squeeze(0)).enumerate_support()
        assert_equal(s.data, self.support_non_vec)

    def test_support(self):
        s = dist.Categorical(self.d_ps).enumerate_support()
        assert_equal(s.data, self.support)


def wrap_nested(x, dim):
    if dim == 0:
        return x
    return wrap_nested([x], dim-1)


@pytest.fixture(params=[1, 2, 3], ids=lambda x: "dim=" + str(x))
def dim(request):
    return request.param


@pytest.fixture(params=[[0.3, 0.5, 0.2]], ids=None)
def ps(request):
    return request.param


def modify_params_using_dims(ps, dim):
    return torch.tensor(wrap_nested(ps, dim-1))


def test_support_dims(dim, ps):
    ps = modify_params_using_dims(ps, dim)
    support = dist.Categorical(ps).enumerate_support()
    assert_equal(support.size(), torch.Size((ps.size(-1),) + ps.size()[:-1]))


def test_sample_dims(dim, ps):
    ps = modify_params_using_dims(ps, dim)
    sample = dist.Categorical(ps).sample()
    expected_shape = dist.Categorical(ps).shape()
    assert_equal(sample.size(), expected_shape)


def test_batch_log_dims(dim, ps):
    ps = modify_params_using_dims(ps, dim)
    log_prob_shape = torch.Size((3,) + dist.Categorical(ps).batch_shape)
    support = dist.Categorical(ps).enumerate_support()
    log_prob = dist.Categorical(ps).log_prob(support)
    assert_equal(log_prob.size(), log_prob_shape)
