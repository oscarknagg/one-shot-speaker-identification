import time
import os
from keras.optimizers import Adam

from utils import whiten, evaluate_siamese_network
from models import get_baseline_convolutional_encoder, build_siamese_net
from data import LibriSpeechDataset
from config import LIBRISPEECH_SAMPLING_RATE


# Mute excessively verbose Tensorflow output
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


##############
# Parameters #
##############
n_seconds = 3
downsampling = 4
batchsize = 32
model_n_filters = 32
model_embedding_dimension = 128
training_set = ['train-clean-100', 'train-clean-360']
validation_set = 'dev-clean'
num_epochs = 25
evaluate_every_n_batches = 500
num_evaluation_tasks = 500
n_shot_classification = 1
k_way_classification = 5

# Derived parameters
input_length = int(LIBRISPEECH_SAMPLING_RATE * n_seconds / downsampling)


###################
# Create datasets #
###################
train_sequence = LibriSpeechDataset(training_set, n_seconds)
valid_sequence = LibriSpeechDataset(validation_set, n_seconds, stochastic=False)


################
# Define model #
################
encoder = get_baseline_convolutional_encoder(model_n_filters, model_embedding_dimension)
siamese = build_siamese_net(encoder, (input_length, 1))
opt = Adam(clipnorm=1.)
siamese.compile(loss='binary_crossentropy', optimizer=opt, metrics=['accuracy'])


###########################
# Define helper functions #
###########################
def preprocessor(downsampling, whitening=True):
    def preprocessor_(batch):
        ([i_1, i_2], labels) = batch
        i_1 = i_1[:, ::downsampling, :]
        i_2 = i_2[:, ::downsampling, :]
        if whitening:
            i_1, i_2 = whiten(i_1), whiten(i_2)

        return [i_1, i_2], labels

    return preprocessor_


whiten_downsample = preprocessor(downsampling, whitening=True)
train_generator = (whiten_downsample(batch) for batch in train_sequence.yield_verification_batches(batchsize))
valid_generator = (whiten_downsample(batch) for batch in valid_sequence.yield_verification_batches(batchsize))


#################
# Training Loop #
#################
t0 = time.time()
print('\n[Batches, Seconds]')
# TODO: Faster creation of verification batches in order to get 100% GPU usage
for n_epoch in range(num_epochs):
    siamese.fit_generator(
        generator=train_generator,
        steps_per_epoch=evaluate_every_n_batches,
        validation_data=valid_generator,
        validation_steps=100,
        epochs=n_epoch + 1,
        workers=4,
        initial_epoch=n_epoch,
        use_multiprocessing=True
    )

    n_correct = evaluate_siamese_network(siamese, valid_sequence, whiten_downsample, num_evaluation_tasks,
                                         n_shot_classification, k_way_classification)

    print('[{:5d}, {:3f}] {:3f} val_oneshot_acc'.format(
        (n_epoch + 1) * evaluate_every_n_batches,
        time.time() - t0,
        n_correct * 1. / num_evaluation_tasks
    ))
