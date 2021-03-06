import math

import chainer
import chainer.functions as F
import chainer.links as L
import numpy as np
from chainer import distributions

class MDN(chainer.Chain):

    """Mixture Density Network."""

    def __init__(self, input_dim, hidden_units, gaussian_mixtures):
        super(MDN, self).__init__()
        with self.init_scope():
            self.l1 = L.Linear(None, hidden_units)
            self.l2 = L.Linear(hidden_units, gaussian_mixtures +
                               gaussian_mixtures * input_dim * 2)  # pi, mu, log_var
        self.input_dim = input_dim
        self.gaussian_mixtures = gaussian_mixtures

    def get_gaussian_params(self, x):
        h = F.tanh(self.l1(x))
        h = self.l2(h)

        pi = h[:, :self.gaussian_mixtures]
        mu_var_dim = self.gaussian_mixtures * self.input_dim
        mu = h[:, self.gaussian_mixtures:self.gaussian_mixtures + mu_var_dim]
        log_var = h[:, self.gaussian_mixtures + mu_var_dim:]

        n_batch = x.shape[0]

        # mixing coefficients
        pi = F.reshape(pi, (n_batch, self.gaussian_mixtures))
        pi = F.softmax(pi, axis=1)

        # mean
        mu = F.reshape(mu, (n_batch, self.gaussian_mixtures, self.input_dim))

        # log variance
        log_var = F.reshape(
            log_var, (n_batch, self.gaussian_mixtures, self.input_dim))

        return pi, mu, log_var

    def negative_log_likelihood(self, x, y):
        pi, mu, log_var = self.get_gaussian_params(x)

        # Likelihood over different Gaussians
        y = F.tile(y[:, None, :], (1, self.gaussian_mixtures, 1))
        pi = F.tile(F.expand_dims(pi, 2), (1, 1, self.input_dim))
        
        squared_sigma = F.exp(log_var)
        sigma = F.sqrt(squared_sigma)
        prob = F.sum(pi * distributions.Normal(mu, sigma).prob(y), axis=1)
        
        negative_log_likelihood = -F.log(prob)
        return F.mean(negative_log_likelihood)

    def sample(self, x):
        pi, mu, log_var = self.get_gaussian_params(x)
        n_batch = pi.shape[0]

        # Choose one of Gaussian means and vars n_batch times
        ps = chainer.backends.cuda.to_cpu(pi.array)
        idx = [np.random.choice(self.gaussian_mixtures, p=p) for p in ps]
        mu = F.get_item(mu, [range(n_batch), idx])
        log_var = F.get_item(log_var, [range(n_batch), idx])

        # Sampling
        z = F.gaussian(mu, log_var)

        return z
