from caffe2.python import cnn

# model = cnn.CNNModelHelper()
def add_ShuffleNet_V2(model, output_channels=[24, 48, 96, 192, 1024],
                      stride_1_repeat_times=[3, 7, 3],
                      stride_2_repeat_times=[1, 1, 1],
                      testing=False,
                      detection=False):
    """Buil a shuffle net.

    Arguments:
        model (CNNModelHelper): the detection/classification model to use
        output_channels (list): the output channels of each stage
        stride_1(2)_repeat_times (list): the replication times of the block in each stage
        testing (bool): build model for testing or training
        detection (bool): build model for detection. If ture, an additional 3x3 depthwise convolution 
            would be added before the first pointwise convolution in each building block.
    """
    s, dim_in = basic_stem(model, 'data', output_channels[0])
    for idx, (dim_out, n_stride_1, n_stride_2) in enumerate(zip(output_channels[1:4],
                       stride_1_repeat_times, stride_2_repeat_times)):
        for i in range(n_stride_2):
            s, dim_in = add_block_stride_2(model, 'stage_' + str(idx+2)
                                           + '_stride2_' + str(i+1)
                                           , s, dim_in, dim_out, testing, detection)
        for i in range(n_stride_1):
            s, dim_in = add_block_stride_1(model, 'stage_' + str(idx+2)
                                           + '_stride1_' + str(i+1)
                                           , s, dim_in, dim_out, testing, detection)

    s = model.Conv(s, 'conv_5', dim_in, output_channels[4], 1)
    s = model.AveragePool(s, 'avg_pooled', kernel=7)
    s = model.FC(s, 'fc', output_channels[4], 1000)
    # scale = 0.03125 # 1. / 32. from 224*224 to 7*7
    return s, 1000

def basic_stem(model, data, dim_out=24):
    p = model.Conv(data, 'conv_1', 3, dim_out, 3, stride=2)
    p = model.MaxPool(p, 'pool_1', stride=2, kernel=3)
    return p, dim_out

def add_block_stride_2(model, prefix, blob_in, dim_in, dim_out, testing=False, detection=True):
    dim_out = int(dim_out / 2)
    right = left = blob_in

    if detection:
        right = model.Conv(right, prefix + '_right_conv_d', dim_in, dim_in, 3, group=dim_in, pad=1) # Enlarge the receptive field for detection task
        right = model.SpatialBN(right, right + '_bn', dim_in, epsilon=1e-3, is_test=testing)

    right = model.Conv(right, prefix + '_right_conv_1', dim_in, dim_in, 1)
    right = model.SpatialBN(right, right + '_bn', dim_in, epsilon=1e-3, is_test=testing)
    right = model.Relu(right, right)
    right = model.Conv(right, prefix + '_right_dwconv', dim_in, dim_in, 3, stride=2, group=dim_in, pad=1)
    right = model.SpatialBN(right, right + '_bn', dim_in, epsilon=1e-3, is_test=testing)
    right = model.Conv(right, prefix + '_right_conv_3', dim_in, dim_out, 1)
    right = model.SpatialBN(right, right + '_bn', dim_out, epsilon=1e-3, is_test=testing)
    right = model.Relu(right, right)

    if detection:
        left = model.Conv(left, prefix + '_left_conv_d', dim_in, dim_in, 3, group=dim_in, pad=1) # Enlarge the receptive field for detection task
        left = model.SpatialBN(left, right + '_bn', dim_in, epsilon=1e-3, is_test=testing)

    left = model.Conv(left, prefix + '_left_dwconv', dim_in, dim_in, 3, stride=2, group=dim_in, pad=1)
    left = model.SpatialBN(left, left + '_bn', dim_in, epsilon=1e-3, is_test=False)
    left = model.Conv(left, prefix + '_left_conv_1', dim_in, dim_out, 1)
    left = model.SpatialBN(left, left + '_bn', dim_out, epsilon=1e-3, is_test=False)
    left = model.Relu(left, left)

    concated = model.Concat([right, left], prefix + '_concated')
    shuffled = model.net.ChannelShuffle(concated, prefix + '_shuffled')
    return shuffled, dim_out * 2

def add_block_stride_1(model, prefix, blob_in, dim_in, dim_out, testing=False, detection=True):
    dim_in = int(dim_in / 2)
    dim_out = int(dim_out / 2)
    model.net.Split(blob_in, [prefix + '_left', prefix + '_right'])

    right = prefix + '_right'
    if detection:
        right = model.Conv(right, prefix + '_right_conv_d', dim_in, dim_in, 3, group=dim_in, pad=1) # Enlarge the receptive field for detection task
        right = model.SpatialBN(right, right + '_bn', dim_in, epsilon=1e-3, is_test=testing)

    right = model.Conv(right, prefix + '_right_conv_1', dim_in, dim_in, 1)
    right = model.SpatialBN(right, right + '_bn', dim_in, epsilon=1e-3, is_test=False)
    right = model.Relu(right, right)
    right = model.Conv(right, prefix + '_right_dwconv', dim_in, dim_in, 3, stride=1, group=dim_in, pad=1)
    right = model.SpatialBN(right, right + '_bn', dim_in, epsilon=1e-3, is_test=False)
    right = model.Conv(right, prefix + '_right_conv_3', dim_in, dim_out, 1)
    right = model.SpatialBN(right, right + '_bn', dim_out, epsilon=1e-3, is_test=False)
    right = model.Relu(right, right)

    concated = model.Concat([right, prefix + '_left'], prefix + '_concated')
    shuffled = model.net.ChannelShuffle(concated, prefix + '_shuffled')

    return shuffled, dim_out * 2
