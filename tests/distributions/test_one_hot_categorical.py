from __future__ import absolute_import, division, print_function

from unittest import TestCase

import numpy as np
import pytest
import torch

import pyro.distributions as dist
from tests.common import assert_equal


class TestOneHotCategorical(TestCase):
    """
    Tests methods specific to the OneHotCategorical distribution
    """

    def setUp(self):
        n = 1
        self.ps = torch.tensor([0.1, 0.6, 0.3])
        self.batch_ps = torch.tensor([[0.1, 0.6, 0.3], [0.2, 0.4, 0.4]])
        self.n = torch.tensor([n])
        self.test_data = torch.tensor([0, 1, 0])
        self.test_data_nhot = torch.tensor([2])
        self.analytic_mean = n * self.ps
        one = torch.ones(3)
        self.analytic_var = n * torch.mul(self.ps, one.sub(self.ps))

        # Discrete Distribution
        self.d_ps = torch.tensor([[0.2, 0.3, 0.5], [0.1, 0.1, 0.8]])
        self.d_test_data = torch.tensor([[0], [5]])
        self.d_v_test_data = [['a'], ['f']]

        self.n_samples = 50000

        self.support_one_hot_non_vec = torch.tensor([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        self.support_one_hot = torch.tensor([[[1, 0, 0], [1, 0, 0]],
                                             [[0, 1, 0], [0, 1, 0]],
                                             [[0, 0, 1], [0, 0, 1]]])
        self.support_non_vec = torch.LongTensor([[0], [1], [2]])
        self.support = torch.LongTensor([[[0], [0]], [[1], [1]], [[2], [2]]])
        self.discrete_support_non_vec = torch.tensor([[0], [1], [2]])
        self.discrete_support = torch.tensor([[[0], [3]], [[1], [4]], [[2], [5]]])
        self.discrete_arr_support_non_vec = [['a'], ['b'], ['c']]
        self.discrete_arr_support = [[['a'], ['d']], [['b'], ['e']], [['c'], ['f']]]

    def test_support_non_vectorized(self):
        s = dist.OneHotCategorical(self.d_ps[0].squeeze(0)).enumerate_support()
        assert_equal(s.data, self.support_one_hot_non_vec)

    def test_support(self):
        s = dist.OneHotCategorical(self.d_ps).enumerate_support()
        assert_equal(s.data, self.support_one_hot)


def wrap_nested(x, dim):
    if dim == 0:
        return x
    return wrap_nested([x], dim-1)


def assert_correct_dimensions(sample, ps):
    ps_shape = list(ps.data.size())
    sample_shape = list(sample.shape)
    assert_equal(sample_shape, ps_shape)


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
    support = dist.OneHotCategorical(ps).enumerate_support()
    for s in support:
        assert_correct_dimensions(s, ps)


def test_sample_dims(dim, ps):
    ps = modify_params_using_dims(ps, dim)
    sample = dist.OneHotCategorical(ps).sample()
    assert_correct_dimensions(sample, ps)


def test_batch_log_dims(dim, ps):
    batch_pdf_shape = (3,) + (1,) * (dim-1)
    expected_log_prob_sum = np.array(wrap_nested(list(np.log(ps)), dim-1)).reshape(*batch_pdf_shape)
    ps = modify_params_using_dims(ps, dim)
    support = dist.OneHotCategorical(ps).enumerate_support()
    log_prob = dist.OneHotCategorical(ps).log_prob(support)
    assert_equal(log_prob.detach().cpu().numpy(), expected_log_prob_sum)
