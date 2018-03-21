import torch

import pyro
import pyro.distributions as dist
import pyro.optim as optim
import pyro.poutine as poutine
import pytest
from pyro.infer import SVI, ADVIDiagonalNormal, ADVIMultivariateNormal
from tests.common import assert_equal
from tests.integration_tests.test_conjugate_gaussian_models import GaussianChain


# simple test model to test ADVI guide construction
def test_model():
    pyro.sample("z1", dist.Normal(0.0, 1.0))
    pyro.sample("z2", dist.Normal(torch.zeros(3), 2.0 * torch.ones(3)))


@pytest.mark.parametrize("advi_implementation", [ADVIMultivariateNormal, ADVIDiagonalNormal])
def test_advi_scores(advi_implementation):
    advi = advi_implementation(test_model)
    guide_trace = poutine.trace(advi.guide).get_trace()
    model_trace = poutine.trace(poutine.replay(advi.model, guide_trace)).get_trace()

    guide_trace.compute_batch_log_pdf()
    model_trace.compute_batch_log_pdf()

    assert model_trace.nodes['_advi_latent']['log_pdf'].item() == 0.0
    assert model_trace.nodes['z1']['log_pdf'].item() != 0.0
    assert guide_trace.nodes['_advi_latent']['log_pdf'].item() != 0.0
    assert guide_trace.nodes['z1']['log_pdf'].item() == 0.0


# conjugate model to test ADVI logic from end-to-end (this has a non-mean-field posterior)
class ADVIGaussianChain(GaussianChain):

    # this is gross but we need to convert between different posterior factorizations
    def compute_target(self, N):
        self.target_advi_mus = torch.zeros(N + 1)
        self.target_advi_diag_cov = torch.zeros(N + 1)
        self.target_advi_mus[-1] = self.target_mus[N].item()
        self.target_advi_diag_cov[-1] = 1.0 / self.lambda_posts[-1].item()
        for n in range(N - 1, 0, -1):
            self.target_advi_mus[n] += self.target_mus[n].item()
            self.target_advi_mus[n] += self.target_kappas[n].item() * self.target_advi_mus[n + 1]
            self.target_advi_diag_cov[n] += 1.0 / self.lambda_posts[n].item()
            self.target_advi_diag_cov[n] += (self.target_kappas[n].item() ** 2) * self.target_advi_diag_cov[n + 1]

    def test_multivariatate_normal_advi(self):
        self.do_test_advi(3, reparameterized=True, n_steps=10001)

    def do_test_advi(self, N, reparameterized, n_steps):
        print("\nGoing to do ADVIGaussianChain test...")
        pyro.clear_param_store()
        self.setUp()
        self.setup_chain(N)
        self.compute_target(N)
        self.advi = ADVIMultivariateNormal(self.model)
        print("target advi_loc:", self.target_advi_mus[1:].detach().numpy())
        print("target advi_diag_cov:", self.target_advi_diag_cov[1:].detach().numpy())

        # TODO speed up with parallel num_particles > 1
        adam = optim.Adam({"lr": .0005, "betas": (0.95, 0.999)})
        svi = SVI(self.advi.model, self.advi.guide, adam, loss="ELBO", trace_graph=False)

        for k in range(n_steps):
            svi.step(reparameterized)

            if k % 1000 == 0 and k > 0 or k == n_steps - 1:
                print("[step %d] advi mean parameter:" % k, pyro.param("advi_loc").detach().numpy())
                L = pyro.param("advi_lower_cholesky")
                diag_cov = torch.mm(L, L.t()).diag()
                print("[step %d] advi_diag_cov:" % k, diag_cov.detach().numpy())

        assert_equal(pyro.param("advi_loc"), self.target_advi_mus[1:], prec=0.05,
                     msg="advi mean off")
        assert_equal(diag_cov, self.target_advi_diag_cov[1:], prec=0.07,
                     msg="advi covariance off")