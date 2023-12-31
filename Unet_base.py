from __future__ import print_function
import torch
import torch.nn as nn


class Up(nn.Module):
    def __init__(self, down_in_channels, in_channels, out_channels, conv_block, interpolation=False, net_mode='2d'):
        super(Up, self).__init__()

        if net_mode == '2d':
            inter_mode = 'bilinear'
            trans_conv = nn.ConvTranspose2d
        elif net_mode == '3d':
            inter_mode = 'trilinear'
            trans_conv = nn.ConvTranspose3d
        else:
            inter_mode = None
            trans_conv = None

        if interpolation == True:
            self.up = nn.Upsample(scale_factor=2, mode=inter_mode, align_corners=True)
        else:
            self.up = trans_conv(down_in_channels, down_in_channels, 2, stride=2)

        self.conv = RecombinationBlock(in_channels + down_in_channels, out_channels, net_mode=net_mode)

    def forward(self, down_x, x):
        up_x = self.up(down_x)

        x = torch.cat((up_x, x), dim=1)

        x = self.conv(x)

        return x


class Down(nn.Module):
    def __init__(self, in_channels, out_channels, conv_block, net_mode='2d'):
        super(Down, self).__init__()
        if net_mode == '2d':
            maxpool = nn.MaxPool2d
        elif net_mode == '3d':
            maxpool = nn.MaxPool3d
        else:
            maxpool = None

        self.conv = RecombinationBlock(in_channels, out_channels, net_mode=net_mode)

        self.down = maxpool(2, stride=2)

    def forward(self, x):
        x = self.conv(x)
        out = self.down(x)

        return x, out


class RecombinationBlock(nn.Module):
    def __init__(self, in_channels, out_channels, batch_normalization=True, kernel_size=3, net_mode='2d'):
        super(RecombinationBlock, self).__init__()

        if net_mode == '2d':
            conv = nn.Conv2d
            bn = nn.BatchNorm2d
        elif net_mode == '3d':
            conv = nn.Conv3d
            bn = nn.BatchNorm3d
        else:
            conv = None
            bn = None

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.bach_normalization = batch_normalization
        self.kerenl_size = kernel_size
        self.rate = 2
        self.expan_channels = self.out_channels * self.rate

        self.expansion_conv = nn.Sequential(conv(self.in_channels, self.expan_channels, 1),
                                            nn.BatchNorm2d(self.expan_channels),
                                            nn.ReLU(inplace=True))
        self.skip_conv = nn.Sequential(conv(self.in_channels, self.out_channels, 1),
                                       nn.BatchNorm2d(self.out_channels),
                                       nn.ReLU(inplace=True))
        self.zoom_conv = nn.Sequential(conv(self.out_channels * self.rate, self.out_channels, 1),
                                       nn.BatchNorm2d(self.out_channels),
                                       nn.ReLU(inplace=True))

        self.bn = bn(self.expan_channels)
        self.norm_conv = nn.Sequential(conv(self.expan_channels, self.expan_channels, self.kerenl_size, padding=1),
                                       nn.BatchNorm2d(self.expan_channels),
                                       nn.ReLU(inplace=True))

    def forward(self, input):
        x = self.expansion_conv(input)

        for i in range(1):
            if self.bach_normalization:
                x = self.bn(x)
            x = nn.ReLU6()(x)
            x = self.norm_conv(x)

        x = self.zoom_conv(x)

        skip_x = self.skip_conv(input)
        out = x + skip_x

        return out


class UNet(nn.Module):
    def __init__(self, in_channels, filter_num_list, class_num, conv_block=RecombinationBlock, net_mode='2d'):
        super(UNet, self).__init__()

        if net_mode == '2d':
            conv = nn.Conv2d
        elif net_mode == '3d':
            conv = nn.Conv3d
        else:
            conv = None

        self.inc = conv(in_channels, 16, 1)

        # down
        self.down1 = Down(16, filter_num_list[0], conv_block=conv_block, net_mode=net_mode)
        self.down2 = Down(filter_num_list[0], filter_num_list[1], conv_block=conv_block, net_mode=net_mode)
        self.down3 = Down(filter_num_list[1], filter_num_list[2], conv_block=conv_block, net_mode=net_mode)
        self.down4 = Down(filter_num_list[2], filter_num_list[3], conv_block=conv_block, net_mode=net_mode)

        self.bridge = conv_block(filter_num_list[3], filter_num_list[4], net_mode=net_mode)

        # up
        self.up1 = Up(filter_num_list[4], filter_num_list[3], filter_num_list[3], conv_block=conv_block,
                      net_mode=net_mode)
        self.up2 = Up(filter_num_list[3], filter_num_list[2], filter_num_list[2], conv_block=conv_block,
                      net_mode=net_mode)
        self.up3 = Up(filter_num_list[2], filter_num_list[1], filter_num_list[1], conv_block=conv_block,
                      net_mode=net_mode)
        self.up4 = Up(filter_num_list[1], filter_num_list[0], filter_num_list[0], conv_block=conv_block,
                      net_mode=net_mode)

        self.class_conv = conv(filter_num_list[0], class_num, 1)

    def forward(self, input):

        x = input

        x = self.inc(x)

        conv1, x = self.down1(x)

        conv2, x = self.down2(x)

        conv3, x = self.down3(x)

        conv4, x = self.down4(x)

        x = self.bridge(x)

        x = self.up1(x, conv4)

        x = self.up2(x, conv3)

        x = self.up3(x, conv2)

        x = self.up4(x, conv1)

        x = self.class_conv(x)

        return x


def main():
    torch.cuda.set_device(0)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  # PyTorch v0.4.0
    model = UNet(1, [32, 48, 64, 96, 128], 1, net_mode='2d').to(device)
    x = torch.rand(1, 1, 256, 256)
    x = x.to(device)
    y = model(x)
    print(y.shape)


if __name__ == '__main__':
    main()