# coding=utf-8
"""Module providing functionality for building convolutional neural nets."""

import tensorflow as tf
from collections import defaultdict


class CNNBuilder(object):
    """Implements logic to build a deep CNN.

    The CNNBuilder object is initiated by providing basic information about
    the network it is building. As the various methods are called,
    it keeps track of the current layer in the model, allowing it to easily
    build up a network, layer by layer.

    All functions must properly update the current top layer and its number
    of channels, as well as return them, in order for the model to work
    properly and be able to interface with custom created layers.
    """

    def __init__(self, input_layer, num_input_channels, is_train_phase,
                 padding_mode='SAME', data_format='NCHW',
                 data_type=tf.float32):
        self.top_layer = input_layer
        self.num_top_channels = num_input_channels
        self.is_train_phase = is_train_phase
        self.padding_mode = padding_mode
        self.data_format = data_format
        self.data_type = data_type
        self.layer_counts = defaultdict(int)

    def _get_name(self, prefix):
        """Creates unique name from prefix based on number of layers in
        network, and updates the layer count."""
        name = '{0:s}{1:d}'.format(prefix, self.layer_counts[prefix])
        self.layer_counts[prefix] += 1
        return name

    def add_layer(self, layer, num_layer_channels):
        """Adds custom layer to model.

         In case a custom layer needed to be created without using one of
         the layer functions available in CNNBuilder, it is necessary to
         call this function afterwards, so that CNNBuilder can add the
         layer's information to its internal representation.

        Args:
            layer: Tensor. New layer to add to model.
            num_layer_channels: int. Number of channels in the layer.

        Returns:
            new_top_layer: Tensor. New top layer of model.
            new_num_top_channels: int. Number of channels in new top layer.
        """
        self.top_layer = layer
        self.num_top_channels = num_layer_channels
        return self.top_layer, self.num_top_channels

    def convolution(self, num_out_channels, filter_height, filter_width,
                    vertical_stride=1, horizontal_stride=1,
                    activation_method='relu'):
        """Adds a convolutional layer to network.

        Args:
            num_out_channels: int. Number of channels in output.
            filter_height: int. Height of filter used for convolution.
            filter_width: int. Width of filter used for convolution.
            vertical_stride: int. Vertical stride.
            horizontal_stride: int. Horizontal stride.
            activation_method: string. Specifies which of the available
                               activation methods in _activation() to use.

        Returns:
            new_top_layer: Tensor. New top layer of model.
            new_num_top_channels: int. Number of channels in new top layer.
        """
        name = self._get_name('conv')
        with tf.variable_scope(name):
            filter_shape = [filter_height, filter_width, self.num_top_channels,
                            num_out_channels]
            filter = cnn_variable('filter', filter_shape,
                                  data_type=self.data_type)
            strides = [1, vertical_stride, horizontal_stride, 1]
            if self.data_format == 'NCHW':
                strides = [strides[0], strides[3], strides[1], strides[2]]
            conv = tf.nn.conv2d(self.top_layer, filter, strides,
                                self.padding_mode,
                                data_format=self.data_format)
            biases = cnn_variable('biases', [num_out_channels], 'zeros',
                                  self.data_type)
            pre_activation = tf.nn.bias_add(conv, biases, self.data_format)
            conv1 = _activation(pre_activation, activation_method)
            self.top_layer = conv1
            self.num_top_channels = num_out_channels
            return self.top_layer, self.num_top_channels

    def dropout(self, keep_prob=0.5):
        """Regularization dropout layer, only applied during training.

        Args:
            keep_prob: float. Probability that any independent neuron will
                       be dropped, if currently in training phase.

        Returns:
            new_top_layer: Tensor. New top layer of model.
            new_num_top_channels: int. Number of channels in new top layer.
        """
        name = self._get_name('dropout')
        if not self.is_train_phase:
            keep_prob = 1.0
        dropped = tf.nn.dropout(self.top_layer, keep_prob, name=name)
        self.top_layer = dropped
        return self.top_layer, self.num_top_channels

    def fully_connected(self, num_out_channels, activation_method='relu'):
        """Adds a fully connected layer to the network.

        Args:
            num_out_channels: int. Number of output neurons.
            activation_method: string. Specifies which of the available
                               activation methods in _activation() to use.

        Returns:
            new_top_layer: Tensor. New top layer of model.
            new_num_top_channels: int. Number of channels in new top layer.
        """
        name = self._get_name('fc')
        with tf.variable_scope(name):
            shape = [self.num_top_channels, num_out_channels]
            weights = cnn_variable('weights', shape, data_type=self.data_type)
            biases = cnn_variable('biases', [num_out_channels], 'zeros',
                                  self.data_type)
            pre_activation = tf.matmul(self.top_layer, weights) + biases
            fc = _activation(pre_activation, activation_method)
            self.top_layer = fc
            self.num_top_channels = num_out_channels
            return self.top_layer, self.num_top_channels

    def max_pooling(self, pool_height, pool_width, vertical_stride=2,
                    horizontal_stride=2):
        """Adds maximum pooling layer to network.

        Args:
            pool_height: int. Height of window used for pooling.
            pool_width: int. Width of window used for pooling.
            vertical_stride: int. Vertical stride.
            horizontal_stride: int. Horizontal stride.

        Returns:
            new_top_layer: Tensor. New top layer of model.
            new_num_top_channels: int. Number of channels in new top layer.
        """
        name = self._get_name('mpool')
        window = [1, pool_height, pool_width, 1]
        strides = [1, vertical_stride, horizontal_stride, 1]
        pool = tf.nn.max_pool(self.top_layer, window, strides,
                              self.padding_mode,
                              self.data_format, name)
        self.top_layer = pool
        return self.top_layer, self.num_top_channels

    def normalization(self, depth_radius=None, bias=None, alpha=None,
                      beta=None):
        """Adds local response normalization layer to network.

        Check TensorFlow local_response_normalization() documentation for
        more information on the parameters.

        Args:
            depth_radius: float. Half-width of the 1-D normalization window.
            bias: float. An offset (usually positive to avoid dividing by 0).
            alpha: float. A scale factor, usually positive.
            beta: float. Defaults to 0.5. An exponent.

        Returns:
            new_top_layer: Tensor. New top layer of model.
            new_num_top_channels: int. Number of channels in new top layer.
        """
        name = self._get_name('norm')
        norm = tf.nn.local_response_normalization(self.top_layer, depth_radius,
                                                  bias, alpha, beta, name)
        self.top_layer = norm
        return self.top_layer, self.num_top_channels

    def reshape(self, shape):
        """Adds a reshape step to the network.

        Args:
            shape: list of ints. Shape to reshape to.

        Returns:
            new_top_layer: Tensor. New top layer of model.
            new_num_top_channels: int. Number of channels in new top layer.
        """
        name = self._get_name('reshape')
        reshaped = tf.reshape(self.top_layer, shape, name)
        self.top_layer = reshaped
        self.num_top_channels = shape[-1]
        return self.top_layer, self.num_top_channels


def cnn_variable(name, shape, init_method='glorot_uniform',
                 data_type=tf.float32):
    """Creates a variable on the CPU device, with options for initialization.

    Args:
        name: Name to use for variable.
        shape: Variable shape.
        init_method: string. Specifies which initialization method to use,
                     as available in _initializer().
        data_type: Data type in output variable.

    Returns:
        A variable placed on the CPU with the specified parameters.
    """
    if not data_type.is_floating:
        return TypeError('Variables must be initialized as floating point.')
    with tf.device('/cpu:0'):
        initializer = _initializer(shape, data_type, init_method)
        variable = tf.get_variable(name, shape, data_type, initializer)
    return variable


def _activation(input_tensor, method):
    method = method or 'linear'
    return {
        'linear': input_tensor,
        'relu': tf.nn.relu(input_tensor),
        'sigmoid': tf.nn.sigmoid(input_tensor),
        'softmax': tf.nn.softmax(input_tensor),
        'tanh': tf.nn.tanh(input_tensor)
    }[method]


def _initializer(shape, data_type, method):
    fan_in = shape[-2] if len(shape) > 1 else shape[-1]
    fan_out = shape[-1]
    for dim in shape[:-2]:
        fan_in *= dim
        fan_out *= dim
    gu_val = (6 / (fan_in + fan_out)) ** 0.5

    method = method or 'zeros'
    return {
        'glorot_uniform': tf.random_uniform_initializer(-gu_val, gu_val,
                                                        dtype=data_type),
        'zeros': tf.zeros_initializer(data_type)
    }[method]
