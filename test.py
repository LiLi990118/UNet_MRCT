import math

import numpy as np
import torch
import tqdm
from skimage.metrics import structural_similarity as ssim
import math
from sklearn.metrics import mean_squared_error, mean_absolute_error
import Unet_base
from torch.utils import data
import data_loader
import os
import SimpleITK as sItk
os.environ['CUDA_VISIBLE_DEVICES'] = '0'


def normalize(img):
    img -= np.min(img)
    img = img / np.max(img)
    return img


def psnr(target, ref):
    target_data = np.array(target, dtype=np.float64)
    ref_data = np.array(ref, dtype=np.float64)
    diff = ref_data - target_data
    diff = diff.flatten('C')
    rmse = math.sqrt(np.mean(diff ** 2.))
    eps = np.finfo(np.float64).eps
    if rmse == 0:
        rmse = eps
    return 55 * math.log10(255.0 / rmse)


def unnor(data, mean,std):
    data = data * np.array(std)
    data += np.array(mean)
    return data


if __name__ == '__main__':
    device = 'cuda'
    weights_path = './weights_base_v1'

    model = Unet_base.UNet(1, [32, 48, 64, 96, 128], 1, net_mode='2d').to(device)
    key = model.load_state_dict(torch.load(weights_path + '/weights.pth', map_location=device))
    model.eval()

    *_, data_test = data_loader.get_data_path()

    val_loader = data.DataLoader(data_loader.Dataset(data_test), batch_size=1,
                                 shuffle=True, num_workers=4)
    ps = []
    mse = []
    mae = []
    s = []
    rmse = []
    for i, (images, labels, ct_mean,ct_std,mr_mean,mr_std,name) in enumerate(tqdm.tqdm(val_loader)):
        images = images.to(device)
        labels = unnor(labels.numpy()[:, 0],ct_mean,ct_std)
        with torch.no_grad():
            outputs = model(images)
        pre = unnor(outputs[:, 0].cpu().numpy(),ct_mean,ct_std)

        yuan_mr = unnor(images[:, 0].cpu().numpy(),mr_mean,mr_std)
        ps.append(psnr(labels, pre))
        labels = labels[0]
        pre = pre[0]
        yuan_mr = yuan_mr[0]

        folder_path = './show/'
        ct_temp = folder_path + name[0] + "-ct"  + '.nii'
        CT_show = sItk.GetImageFromArray(labels)
        sItk.WriteImage(CT_show, ct_temp)

        ct_pre_temp = folder_path + name[0] + "-ct_pre"  + '.nii'
        ct_pre = sItk.GetImageFromArray(pre)
        sItk.WriteImage(ct_pre, ct_pre_temp)

        mr_temp = folder_path + name[0] + "-mr"  + '.nii'
        mr_show = sItk.GetImageFromArray(yuan_mr)
        sItk.WriteImage(mr_show, mr_temp)

        mse.append(mean_squared_error(labels, pre))
        mae.append(mean_absolute_error(labels, pre))
        # nor_label = normalize(labels)
        # nor_pre_ct = normalize(pre)
        s.append(ssim(labels, pre,
                      data_range=4000))
        rmse.append(np.sqrt(mse[-1]))

    print('mean mse is : ', np.mean(mse), '±', np.std(mse))
    print('mean rmse is : ', np.mean(rmse), '±', np.std(rmse))
    print('mean mae is : ', np.mean(mae), '±', np.std(mae))
    print('mean ssim is : ', np.mean(s), '±', np.std(s))
    print('mean psnr is : ', np.mean(ps), '±', np.std(ps))
