import numpy as np
import tensorflow as tf


class agent_model():
    def __init__(self, args, mas_label):
        self.label = mas_label
        self.d_o = args.dim_o
        self.d_a = 2
        self.n_agents = args.n_agents
        self.n_others = self.n_agents - 1
        self.d_a_others = self.n_others * self.d_a
        self.gamma = args.gamma
        self.lr_a = args.lr_a
        self.lr_c = args.lr_c
        self.tau = args.tau
        self.dim_units_a = args.actor_net_h_unit
        self.dim_units_c = args.critic_net_h_unit

        # exploration noise
        self.mu = []
        self.sigma = args.explore_sigma * np.eye(self.d_a, self.d_a)

        # Input and Output For Actor Network
        self.obs_t = tf.placeholder(tf.float32, [None, self.d_o], name=self.label + "obs_t")
        self.obs_tt = tf.placeholder(tf.float32, [None, self.d_o], name=self.label + "obs_next")
        self.act_t = tf.placeholder(tf.float32, [None, self.d_a], name=self.label + "act_t")
        self.act_t = self.actor_net(obs_in=self.obs_t, scope=self.label + "actor_net")
        self.act_tt = self.actor_net(obs_in=self.obs_tt, scope=self.label + "actor_target_net")
        # Input And Output for Critic Network
        self.Q = self.critic_net(obs_in=self.obs_t, act_in=self.act_t,
                                 scope=self.label + "critic_net")
        self.Q_t = self.critic_net(obs_in=self.obs_tt, act_in=self.act_tt,
                                   scope=self.label + "critic_target_net")
        self.Q_target = tf.placeholder(tf.float32, [None, 1], name=self.label + "q_predict")

        # Parameter Collection
        self.a_var = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.label + "actor_net")
        self.c_var = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.label + "critic_net")
        self.a_tar_var = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.label + "actor_target_net")
        self.c_tar_var = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.label + "critic_target_net")

        # loss function and Optimizer
        self.TD_error = self.Q - self.Q_target
        self.loss_c = tf.reduce_mean(tf.square(self.TD_error))
        self.loss_a = tf.reduce_mean(-self.Q)
        self.trainer_c = tf.train.AdamOptimizer(self.lr_c).minimize(self.loss_c, var_list=self.c_var)
        self.trainer_a = tf.train.AdamOptimizer(self.lr_a).minimize(self.loss_a, var_list=self.a_var)

        # soft update for target network
        self.soft_update_a = [self.a_tar_var[i].assign(
            tf.multiply(self.a_var[i], self.tau) + tf.multiply(self.a_tar_var[i], 1 - self.tau)) for i in
            range(len(self.a_tar_var))]
        for i in range(len(self.a_tar_var)):
            self.soft_update_a[i] = tf.assign(self.a_tar_var[i],
                                              tf.multiply(self.a_var[i], self.tau) + tf.multiply(self.a_tar_var[i],
                                                                                                   1 - self.tau))
        self.soft_update_c = [self.c_tar_var[i].assign(
            tf.multiply(self.c_var[i], self.tau) + tf.multiply(self.c_tar_var[i], 1 - self.tau)) for i in
            range(len(self.c_tar_var))]
        for i in range(len(self.c_tar_var)):
            self.soft_update_c[i] = tf.assign(self.c_tar_var[i],
                                              tf.multiply(self.c_var[i], self.tau) + tf.multiply(self.c_tar_var[i],
                                                                                                   1 - self.tau))

        self.reward = tf.placeholder(tf.float32, [None, 1], name=self.label + "reward_t")
        self.r_predict = None

    def actor_net(self, obs_in, scope):
        with tf.variable_scope(scope):
            # hidden layers
            x_in = obs_in
            for idx_layer in range(self.dim_units_a.__len__()):
                layer = tf.layers.dense(
                    inputs=x_in,
                    units=self.dim_units_a[idx_layer],
                    activation=tf.nn.leaky_relu,
                    kernel_initializer=tf.random_normal_initializer(mean=0, stddev=0.03),
                    bias_initializer=tf.constant_initializer(0.0),
                    name='layer_' + str(idx_layer)
                )
                x_in = layer

            # output layer
            output_act = tf.layers.dense(
                inputs=x_in,
                units=self.d_a,
                activation=tf.nn.tanh,
                kernel_initializer=tf.random_uniform_initializer(minval=-0.1, maxval=0.1),
                bias_initializer=tf.constant_initializer(0.0),
                name='layer_output'
            )
        return output_act

    def critic_net(self, obs_in, act_in, scope):
        with tf.variable_scope(scope):
            # hidden layers
            x_in = tf.concat([obs_in, act_in], axis=1)
            for idx_layer in range(self.dim_units_c.__len__()):
                layer = tf.layers.dense(
                    inputs=x_in,
                    units=self.dim_units_c[idx_layer],
                    activation=tf.nn.relu,
                    kernel_initializer=tf.random_normal_initializer(mean=0, stddev=0.03),
                    bias_initializer=tf.constant_initializer(0.1),
                    name='layer_' + str(idx_layer)
                )
                x_in = layer

            # output layer
            output_q = tf.layers.dense(
                inputs=x_in,
                units=1,
                activation=None,
                kernel_initializer=tf.random_uniform_initializer(minval=-0.1, maxval=0.1),
                bias_initializer=tf.constant_initializer(0.1),
                name='layer_output'
            )

            return output_q

    def update_target_net(self, sess, init=False):
        sess.run(self.soft_update_a)
        sess.run(self.soft_update_c)

        if init:
            for i in range(len(self.c_tar_var)):
                sess.run(tf.assign(self.c_tar_var[i], self.c_var[i]))
            for i in range(len(self.a_tar_var)):
                sess.run(tf.assign(self.a_tar_var[i], self.a_var[i]))

    def get_actions(self, obs, sess, noise=False):
        action_t = self.act_t.eval(feed_dict={self.obs_t: obs}, session=sess)
        if noise:
            self.mu = action_t
            for i in range(self.d_a):
                action_t[:, i] = action_t[:, i] + np.random.normal(0, self.sigma[i][i])

        return action_t

    def get_q_values(self, obs, obs_others, act, act_others, sess):
        return self.Q.eval(feed_dict={self.obs_t: obs,
                                      self.act_t: act},
                           session=sess)

    def get_q_predict(self, r, obs_next, sess):
        q_next = self.Q_t.eval(feed_dict={self.obs_tt: obs_next},
                               session=sess)
        q_predict = r + self.gamma * q_next

        return q_predict

