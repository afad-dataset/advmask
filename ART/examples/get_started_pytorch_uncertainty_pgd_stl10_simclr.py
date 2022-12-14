"""
The script demonstrates a simple example of using ART with PyTorch. The example train a small model on the MNIST dataset
and creates adversarial examples using the Fast Gradient Sign Method. Here we use the ART classifier to train the model,
it would also be possible to provide a pretrained model to the ART classifier.
The parameters are chosen for reduced computational requirements of the script and not optimised for accuracy.
"""
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from torch import Tensor
from torch import torch
import copy

from art.attacks.evasion.projected_gradient_descent.projected_gradient_descent import ProjectedGradientDescent
from art.attacks.evasion import FastGradientMethod
from art.estimators.classification import PyTorchClassifier
from art.utils import load_mnist
from art.utils import load_dataset
from art.preactresnet import PreActBlock, PreActBottleneck, PreActResNet, PreActResNet18, initialize_weights, PreActResNet18_
import torchvision.transforms as transforms
from PIL import Image

import numpy as np

def softmax(x, axis):
        """
        x --- 一个二维矩阵, m * n,其中m表示向量个数，n表示向量维度
        """
        assert(len(x.shape) == 2)
        row_max = np.max(x, axis=axis).reshape(-1, 1)
        x -= row_max
        x_exp = np.exp(x)
        s = x_exp / np.sum(x_exp, axis=axis, keepdims=True)

        return s

# Step 0: Define the neural network model, return logits instead of activation in forward method

# Read CIFAR10 dataset
(x_train, y_train), (x_test, y_test), min_, max_ = load_dataset(str("stl10"))
#x_train, y_train = x_train[:5000], y_train[:5000]
x_test, y_test = x_test[:500], y_test[:500]
im_shape = x_train[0].shape



cifar_mu = np.ones((3, 96, 96))
cifar_mu[0, :, :] = 0.4914
cifar_mu[1, :, :] = 0.4822
cifar_mu[2, :, :] = 0.4465


cifar_std = np.ones((3, 96, 96))
cifar_std[0, :, :] = 0.2471
cifar_std[1, :, :] = 0.2435
cifar_std[2, :, :] = 0.2616

x_train = x_train.transpose(0, 3, 1, 2).astype("float32")
x_test = x_test.transpose(0, 3, 1, 2).astype("float32")

transform = transforms.Compose(
            #[transforms.RandomCrop(32, padding=4), transforms.RandomHorizontalFlip(), transforms.ToTensor()]
            #[transforms.RandomResizedCrop(32), transforms.ToTensor()]
            #[transforms.RandomCrop(32), transforms.ToTensor()]
            [transforms.ToTensor()]
            )

print(x_train.shape)
x_train_ = np.ones((x_train.shape[0], 3, 96, 96))
for idx in range(len(x_train)):
    #print(x_train[idx])
    x = Image.fromarray(((x_train[idx] * 255).round()).astype(np.uint8).transpose(1, 2, 0))
    x = transform(x)
    x_train_[idx] = x
    #print(x)

x_train = x_train_.astype("float32")
print(y_train.shape)


print(x_test.shape)
x_test_ = np.ones((x_test.shape[0], 3, 96, 96))
for idx in range(len(x_test)):
    #print(x_train[idx])
    x = Image.fromarray(((x_test[idx] * 255).round()).astype(np.uint8).transpose(1, 2, 0))
    x = transform(x)
    x_test_[idx] = x
    #print(x)

x_test = x_test_.astype("float32")
print(y_test.shape)



class _Loss(nn.Module):
    reduction: str

    def __init__(self, size_average=None, reduce=None, reduction: str = 'mean') -> None:
        super(_Loss, self).__init__()
        if size_average is not None or reduce is not None:
            self.reduction: str = _Reduction.legacy_get_string(size_average, reduce)


class _Loss(nn.Module):
    reduction: str

    def __init__(self, size_average=None, reduce=None, reduction: str = 'mean') -> None:
        super(_Loss, self).__init__()
        if size_average is not None or reduce is not None:
            self.reduction: str = _Reduction.legacy_get_string(size_average, reduce)
        else:
            self.reduction = reduction

class MyLoss(_Loss):
    __constants__ = ['reduction']

    def __init__(self, size_average=None, reduce=None, reduction: str = 'mean') -> None:
        super(MyLoss, self).__init__(size_average, reduce, reduction)

    #def forward(self, input: Tensor, target: Tensor) -> Tensor:
    #    return F.mse_loss(input, target, reduction=self.reduction)
    def forward(self, input: Tensor, target: Tensor) -> Tensor:
        #print(input.size())
        #print(target.size())
        #print(input[0])
        #print(target[0])
        #input2 = F.log_softmax(input)
        #input2 = F.softmax(input)
        (var, mean) = torch.var_mean(input, 1, unbiased=False, keepdim=True)
        #print(np.shape(var))
        #print(var)

        (var2, mean2) = torch.var_mean(var, unbiased=False)
        #print(mean2)
        return -1 * mean2
        #return  mean2
        #return F.nll_loss(input, target, reduction='mean')



lod = torch.load('/art/SimCLR/pre-training-model/stl/checkpoint_0206.pth.tar')
print(lod.keys())
lod_state = lod['state_dict']

class ResNetSimCLR_ft(nn.Module):

    def __init__(self, base_model, out_dim):
        super(ResNetSimCLR_ft, self).__init__()

        self.backbone = PreActResNet18()
        #dim_mlp = self.backbone.fc.in_features
        dim_mlp = self.backbone.linear.in_features

        # add mlp projection head
        #self.backbone.fc = nn.Sequential(nn.Linear(dim_mlp, dim_mlp), nn.ReLU(), self.backbone.fc)
        #self.backbone.linear = nn.Sequential(nn.Linear(dim_mlp, dim_mlp), nn.ReLU(), self.backbone.linear)
        self.backbone.linear = nn.Linear(in_features=dim_mlp, out_features=10)


    def forward(self, x):
        x = self.backbone(x)
        x = F.log_softmax(x)
        return x


# Step 2: create the PyTorch model
#model = PreActResNet18()
#model = PreActResNet18_()
#model.apply(initialize_weights)
model = ResNetSimCLR_ft(base_model=None, out_dim=128)
model.train()
#model.load_state_dict(lod_state)

'''
###load
model_dict = model.state_dict()
state_dict = {k:v for k,v in lod_state.items() if k in model_dict.keys()}
#print(state_dict.keys())
model_dict.update(state_dict)
model.load_state_dict(model_dict)



for k,v in model.named_parameters():
    #print(k)
    #v.requires_grad = False
    v.requires_grad = True

model.backbone.linear.weight.requires_grad = True
model.backbone.linear.bias.requires_grad = True
'''
for k,v in model.named_parameters():
    print(k)
    print(v.requires_grad)
    #print(v)


#opt = optim.Adam(model.parameters(), lr=0.01)
opt = torch.optim.SGD(model.parameters(), lr=0.1, momentum=0.9, weight_decay=5e-4)
#opt = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.9, weight_decay=5e-4)
#criterion = nn.CrossEntropyLoss()
criterion = nn.NLLLoss()

#model_ft = torch.load('/art/model_stl/clr/model_clr_dim16.model')
#model.load_state_dict(model_ft)


# Step 3: Create the ART classifier
classifier = PyTorchClassifier(
            model=model,
            clip_values=(0.0, 1.0),
            preprocessing=(cifar_mu, cifar_std),
            loss=criterion,
            optimizer=opt,
            input_shape=(3, 96, 96),
            nb_classes=10,
            )


#predictions = classifier.predict(x_test)
#accuracy = np.sum(np.argmax(predictions, axis=1) == np.argmax(y_test, axis=1)) / len(y_test)
#print("Pre-training accuracy on benign test examples: {}%".format(accuracy * 100))


# Step 4: Train the ART classifier
classifier.fit(x_train, y_train, batch_size=64, nb_epochs=50)

# Step 5: Evaluate the ART classifier on benign test examples
predictions = classifier.predict(x_test)

#print(np.exp(predictions[0:2]))
#maxv = np.max(np.exp(predictions), axis=1)
#print(maxv[0:10])
#mean2 = np.mean(maxv)
#print(mean2)

accuracy = np.sum(np.argmax(predictions, axis=1) == np.argmax(y_test, axis=1)) / len(y_test)
print("FT accuracy on benign test examples: {}%".format(accuracy * 100))
#classifier.save('model_clr_dim16','/art/model_cifar/clr/')
classifier.save('model_scratch_dim16','/art/model_stl/clr/')









#####
#attack = FastGradientMethod(estimator=classifier, eps=0.2)
#attack = ProjectedGradientDescent(classifier, eps=1.0, eps_step=0.1, verbose=False)
#attack = ProjectedGradientDescent(classifier, eps=0.2, eps_step=0.1, verbose=False)
attack = ProjectedGradientDescent(
            classifier,
            norm=np.inf,
            eps=8.0 / 255.0,
            eps_step=2.0 / 255.0,
            max_iter=40,
            targeted=False,
            num_random_init=5,
            batch_size=32,
            )

x_test_adv = attack.generate(x=x_test)
predictions = classifier.predict(x_test_adv)

#print(np.exp(predictions[0:2]))
#maxv = np.max(np.exp(predictions), axis=1)
#print(maxv[0:10])
#mean2 = np.mean(maxv)
#print(mean2)

accuracy = np.sum(np.argmax(predictions, axis=1) == np.argmax(y_test, axis=1)) / len(y_test)
print("PGD attack: Accuracy on adversarial test examples: {}%".format(accuracy * 100))


print("----Uncertainty attack----")

class ResNetSimCLR_ft_uncertainty(nn.Module):

    def __init__(self, base_model, out_dim):
        super(ResNetSimCLR_ft_uncertainty, self).__init__()

        self.backbone = PreActResNet18()
        #dim_mlp = self.backbone.fc.in_features
        dim_mlp = self.backbone.linear.in_features

        # add mlp projection head
        #self.backbone.fc = nn.Sequential(nn.Linear(dim_mlp, dim_mlp), nn.ReLU(), self.backbone.fc)
        #self.backbone.linear = nn.Sequential(nn.Linear(dim_mlp, dim_mlp), nn.ReLU(), self.backbone.linear)
        self.backbone.linear = nn.Linear(in_features=dim_mlp, out_features=10)


    def forward(self, x):
        x = self.backbone(x)
        #x = F.log_softmax(x)
        return x

# Step 2: create the PyTorch model
#model = PreActResNet18()
#model = PreActResNet18_()
# Step 2: create the PyTorch model
#model2 = PreActResNet18()
#model2 = PreActResNet18_()
#model2 = ResNetSimCLR_ft(base_model=None, out_dim=128)
model2 = ResNetSimCLR_ft_uncertainty(base_model=None, out_dim=128)
model2.train()
#opt2 = optim.Adam(model2.parameters(), lr=0.01)
opt2 = torch.optim.SGD(model2.parameters(), lr=0.01, momentum=0.9, weight_decay=5e-4)

#model_trained = classifier.model()
model_trained = copy.deepcopy(classifier.model)
criterion2 = MyLoss()

model2.load_state_dict(model_trained.state_dict())

classifier2 = PyTorchClassifier(
            model=model2,
            clip_values=(0.0, 1.0),
            preprocessing=(cifar_mu, cifar_std),
            loss=criterion2,
            optimizer=opt2,
            input_shape=(3, 32, 32),
            nb_classes=10,
            )


#predictions = classifier.predict(x_test)
#accuracy = np.sum(np.argmax(predictions, axis=1) == np.argmax(y_test, axis=1)) / len(y_test)
#print("Uncertainty Attack: Accuracy on benign test examples: {}%".format(accuracy * 100))



# Step 6: Generate adversarial test examples
#attack = FastGradientMethod(estimator=classifier2, eps=0.2)
#x_test_adv = attack.generate(x=x_test)

# Test PGD with np.inf norm
#attack = ProjectedGradientDescent(classifier2, eps=1.0, eps_step=0.1, verbose=False)
#attack = ProjectedGradientDescent(classifier2, eps=1.0, eps_step=0.1, verbose=False)
attack = ProjectedGradientDescent(
            classifier2,
            norm=np.inf,
            eps=8.0 / 255.0,
            eps_step=2.0 / 255.0,
            max_iter=40,
            targeted=False,
            num_random_init=5,
            batch_size=32,
            )

x_test_adv = attack.generate(x_test)


# Step 7: Evaluate the ART classifier on adversarial test examples

predictions = classifier.predict(x_test_adv)

#print(np.shape(predictions))
print(np.exp(predictions[0:2]))
#print(softmax(predictions[0:4], 1))

maxv = np.max(np.exp(predictions), axis=1)
#maxv = np.max(softmax(predictions, 1), axis=1)
#print(np.shape(var))
#print(var[0:10])
#print(np.shape(maxv))
print(maxv[0:10])
#mean2 = np.mean(var)
mean2 = np.mean(maxv)
print(mean2)

accuracy = np.sum(np.argmax(predictions, axis=1) == np.argmax(y_test, axis=1)) / len(y_test)
print("Uncertainty Attack: Accuracy on adversarial test examples: {}%".format(accuracy * 100))
