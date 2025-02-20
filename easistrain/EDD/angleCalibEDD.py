import h5py
import numpy as np
import silx.math.fit
import silx.math.fit.peaks
import scipy.optimize
import sympy

# Test modif
# fileRead = '/home/esrf/slim/data/ihme10/id15/Cr2O3_calib/ihme10_Cr2O3_calib.h5'
# filesave = '/home/esrf/slim/easistrain/easistrain/EDD/Results_ihme10_Cr2O3_calib.h5'
# sample = 'Cr2O3_calib'
# dataset = '0001'
# scanNumber = '5'
# nameHorizontalDetector = 'mca2_det0'
# nameVerticalDetector = 'mca2_det1'
# numberOfBoxes  = 7
# nbPeaksInBoxes = [1,2,3,1,2,2,1]
# rangeFitHD = [425,560,640,810,790,980,950,1100,1070,1250,1220,1420,1370,1500]
# rangeFitVD = [425,580,660,830,810,1040,975,1110,1090,1280,1250,1450,1400,1535]
# pathFileDetectorCalibration = '/home/esrf/slim/easistrain/easistrain/EDD/Results_ihme10_align.h5'
# scanDetectorCalibration = 'fit_0001_2_1'
# sampleCalibrantFile = '/home/esrf/slim/easistrain/easistrain/EDD/Cr2O3.d'


def linefunc(a, xData):
    return a * xData


def splitPseudoVoigt(xData, *params):
    return silx.math.fit.sum_splitpvoigt(xData, *params)


def gaussEstimation(xData, *params):
    return silx.math.fit.sum_gauss(xData, *params)


def uChEConversion(a, b, c, ch, ua, ub, uc, uch):
    return np.sqrt(
        ((ua ** 2) * (ch ** 4))
        + ((uch ** 2)) * (((2 * a * ch) + b) ** 2)
        + ((ub ** 2) * ch ** 2)
        + (uc ** 2)
    )  ## calculates the uncertainty on the energy coming from the conversion from channel to energy. It includes the uncertainty on the calibration of the coefficients and the peak position


def calcBackground(
    xData, yData, fwhmRight, fwhmLeft, counterOfBoxes, nbPeaksInBoxes, guessedPeaksIndex
):
    if int(guessedPeaksIndex[0] - 3 * fwhmLeft) < 0 and int(
        guessedPeaksIndex[-1] + 3 * fwhmRight
    ) <= len(
        xData
    ):  ## case of not enough of points at left
        # print('## case of not enough of points at left')
        xBackground = xData[int(guessedPeaksIndex[-1] + 3 * fwhmRight) :]
        yBackground = yData[int(guessedPeaksIndex[-1] + 3 * fwhmRight) :]
    if (
        int(guessedPeaksIndex[-1] + 3 * fwhmRight) > len(xData)
        and int(guessedPeaksIndex[0] - 3 * fwhmLeft) >= 0
    ):  ## case of not enough of points at right
        # print('## case of not enough of points at right')
        xBackground = xData[0 : int(guessedPeaksIndex[0] - 3 * fwhmLeft)]
        yBackground = yData[0 : int(guessedPeaksIndex[0] - 3 * fwhmLeft)]
    if int(guessedPeaksIndex[0] - 3 * fwhmLeft) < 0 and int(
        guessedPeaksIndex[-1] + 3 * fwhmRight
    ) > len(
        xData
    ):  ## case of not enough of points at left and right
        # print('## case of not enough of points at left and right')
        xBackground = np.append(xData[0:5], xData[-5:])
        yBackground = np.append(yData[0:5], yData[-5:])
    if int(guessedPeaksIndex[0] - 3 * fwhmLeft) >= 0 and int(
        guessedPeaksIndex[-1] + 3 * fwhmRight
    ) <= len(
        xData
    ):  ## case of enough of points at left and right
        # print('## case of enough of points at left and right')
        xBackground = np.append(
            xData[0 : int(guessedPeaksIndex[0] - 3 * fwhmLeft)],
            xData[int(guessedPeaksIndex[-1] + 3 * fwhmRight) :],
        )
        yBackground = np.append(
            yData[0 : int(guessedPeaksIndex[0] - 3 * fwhmLeft)],
            yData[int(guessedPeaksIndex[-1] + 3 * fwhmRight) :],
        )
    # print(xData[0:int(guessedPeaksIndex[0] - 3 * fwhmLeft)])
    # print(xData[-int(guessedPeaksIndex[-1] + 3 * fwhmRight):])
    # print(int(guessedPeaksIndex[-1] + 3 * fwhmRight))
    # print(int(guessedPeaksIndex[0] - 3 * fwhmLeft))
    # print(fwhmRight)
    # print(xBackground)
    # print(yBackground)
    backgroundCoefficient = np.polyfit(
        x=xBackground, y=yBackground, deg=1
    )  ## fit of background with 1d polynom function
    yCalculatedBackground = np.poly1d(backgroundCoefficient)(
        xData
    )  ## yBackground calcuated with the 1d polynom fitted coefficient
    return yCalculatedBackground, backgroundCoefficient


def guessParameters(xData, yData, counterOfBoxes, nbPeaksInBoxes):
    p0Guess = np.zeros(3 * nbPeaksInBoxes[counterOfBoxes], float)
    fwhmGuess = silx.math.fit.peaks.guess_fwhm(yData)
    peaksGuess = silx.math.fit.peaks.peak_search(
        yData,
        fwhmGuess,
        sensitivity=2.5,
        begin_index=None,
        end_index=None,
        debug=False,
        relevance_info=False,
    )  ## index of the peak with peak relevance
    # (f'first evaluation of peak guess{peaksGuess}')
    if (
        np.size(peaksGuess) > nbPeaksInBoxes[counterOfBoxes]
    ):  ## case if more peaks than expected are detected
        peaksGuess = silx.math.fit.peaks.peak_search(
            yData,
            fwhmGuess,
            sensitivity=1,
            begin_index=None,
            end_index=None,
            debug=False,
            relevance_info=True,
        )  ## index of the peak with peak relevance
        peaksGuessArray = np.asarray(peaksGuess)
        orderedIndex = np.argsort(peaksGuessArray[:, 1])[
            -nbPeaksInBoxes[counterOfBoxes] :
        ]
        peaksGuess = sorted(peaksGuessArray[orderedIndex[:], 0])  ## peaks indices
    if (
        np.size(peaksGuess) < nbPeaksInBoxes[counterOfBoxes]
    ):  ## case if less peaks than expected are detected
        peaksGuess = silx.math.fit.peaks.peak_search(
            yData,
            fwhmGuess,
            sensitivity=1,
            begin_index=None,
            end_index=None,
            debug=False,
            relevance_info=True,
        )  ## index of the peak with peak relevance
        peaksGuessArray = np.asarray(peaksGuess)
        orderedIndex = np.argsort(peaksGuessArray[:, 1])[
            -nbPeaksInBoxes[counterOfBoxes] :
        ]
        peaksGuess = sorted(peaksGuessArray[orderedIndex[:], 0])  ## peaks indices
    # print(peaksGuess)
    for ipar in range(nbPeaksInBoxes[counterOfBoxes]):
        p0Guess[3 * ipar] = yData[int(peaksGuess[ipar])]
        p0Guess[3 * ipar + 1] = xData[int(peaksGuess[ipar])]
        p0Guess[3 * ipar + 2] = fwhmGuess
    firstGuess, covGuess = scipy.optimize.curve_fit(
        gaussEstimation,
        xData,
        yData,
        p0Guess,
    )
    # print(firstGuess)
    # print(peaksGuess)
    return firstGuess, peaksGuess


### angleCalibrationEDD is the main function
def angleCalibrationEDD(
    fileRead,
    fileSave,
    sample,
    dataset,
    scanNumber,
    nameHorizontalDetector,
    nameVerticalDetector,
    numberOfBoxes,
    nbPeaksInBoxes,
    rangeFitHD,
    rangeFitVD,
    pathFileDetectorCalibration,
    scanDetectorCalibration,
    sampleCalibrantFile,
):
    with h5py.File(fileRead, "r") as h5Read:  ## Read the h5 file of raw data
        patternHorizontalDetector = h5Read[
            sample
            + "_"
            + str(dataset)
            + "_"
            + str(scanNumber)
            + ".1/measurement/"
            + nameHorizontalDetector
        ][
            ()
        ]  ## pattern of horizontal detector
        patternVerticalDetector = h5Read[
            sample
            + "_"
            + str(dataset)
            + "_"
            + str(scanNumber)
            + ".1/measurement/"
            + nameVerticalDetector
        ][
            ()
        ]  ## pattern of vertical detector

    h5Save = h5py.File(fileSave, "a")  ## create/append h5 file to save in
    if not "angleCalibration" in h5Save.keys():
        angleCalibrationLevel1 = h5Save.create_group(
            "angleCalibration"
        )  ## angleCalibration group
    else:
        angleCalibrationLevel1 = h5Save["angleCalibration"]
    rawDataLevel1_1 = angleCalibrationLevel1.create_group(
        "rawData" + "_" + str(dataset) + "_" + str(scanNumber)
    )  ## rawData subgroup in calibration group
    fitLevel1_2 = angleCalibrationLevel1.create_group(
        "fit" + "_" + str(dataset) + "_" + str(scanNumber)
    )  ## fit subgroup in calibration group
    fitLevel1_2.create_group("fitParams")  ## fit results group for the two detector
    fitLevel1_2.create_group(
        "curveAngleCalibration"
    )  ## curve E VS channels group for the two detector
    fitLevel1_2.create_group(
        "calibratedAngle"
    )  ## diffraction angle of the two detectors group for the two detector

    infoGroup = fitLevel1_2.create_group("infos")  ## infos group creation
    infoGroup.create_dataset(
        "fileRead", dtype=h5py.string_dtype(encoding="utf-8"), data=fileRead
    )  ## save path of raw data file in infos group
    infoGroup.create_dataset(
        "fileSave", dtype=h5py.string_dtype(encoding="utf-8"), data=fileSave
    )  ## save path of the file in which results will be saved in info group
    infoGroup.create_dataset(
        "sample", dtype=h5py.string_dtype(encoding="utf-8"), data=sample
    )  ## save the name of the sample in infos group
    infoGroup.create_dataset(
        "dataset", dtype=h5py.string_dtype(encoding="utf-8"), data=dataset
    )  ## save the name of dataset in infos group
    infoGroup.create_dataset(
        "scanNumber", dtype=h5py.string_dtype(encoding="utf-8"), data=scanNumber
    )  ## save of the number of the scan in infos group
    infoGroup.create_dataset(
        "nameHorizontalDetector",
        dtype=h5py.string_dtype(encoding="utf-8"),
        data=nameHorizontalDetector,
    )  ## save of the name of the horizontal detector in infos group
    infoGroup.create_dataset(
        "nameVerticalDetector",
        dtype=h5py.string_dtype(encoding="utf-8"),
        data=nameVerticalDetector,
    )  ## save of the name of the vertical detector in infos group
    infoGroup.create_dataset(
        "numberOfBoxes", dtype="int", data=numberOfBoxes
    )  ## save of the number of the boxes/widows extracted from the raw data in infos group
    infoGroup.create_dataset(
        "nbPeaksInBoxes", dtype="int", data=nbPeaksInBoxes
    )  ## save of the number of peaks per box/window in infos group
    infoGroup.create_dataset(
        "rangeFitHD", dtype="int", data=rangeFitHD
    )  ## save of the range of the fit of each box/window of the horizontal detector in infos group
    infoGroup.create_dataset(
        "rangeFitVD", dtype="int", data=rangeFitVD
    )  ## save of the range of the fit of each box/window of the vertical detector in infos group

    fitParamsHD = np.array(())
    fitParamsVD = np.array(())
    uncertaintyFitParamsHD = np.array(())
    uncertaintyFitParamsVD = np.array(())
    curveAngleCalibrationHD = np.zeros((np.sum(nbPeaksInBoxes), 2), float)
    curveAngleCalibrationVD = np.zeros((np.sum(nbPeaksInBoxes), 2), float)
    for i in range(numberOfBoxes):
        peakHorizontalDetector = np.transpose(
            (
                np.arange(rangeFitHD[2 * i], rangeFitHD[(2 * i) + 1]),
                patternHorizontalDetector[rangeFitHD[2 * i] : rangeFitHD[(2 * i) + 1]],
            )
        )  ## peak of the horizontal detector
        peakVerticalDetector = np.transpose(
            (
                np.arange(rangeFitVD[2 * i], rangeFitVD[(2 * i) + 1]),
                patternVerticalDetector[rangeFitVD[2 * i] : rangeFitVD[(2 * i) + 1]],
            )
        )  ## peak of the vertical detector
        backgroundHorizontalDetector = silx.math.fit.strip(
            data=peakHorizontalDetector[:, 1],
            w=5,
            niterations=4000,
            factor=1,
            anchors=None,
        )  ## stripped background of the horizontal detector (obtained by stripping the yData)
        backgroundVerticalDetector = silx.math.fit.strip(
            data=peakVerticalDetector[:, 1],
            w=5,
            niterations=4000,
            factor=1,
            anchors=None,
        )  ## stripped background of the vertical detector (obtained by stripping the yData)
        fitLevel1_2.create_group(
            f"fitLine_{str(i)}"
        )  ## create group for each calibration peak
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "rawHorizontalDetector", dtype="float64", data=peakHorizontalDetector
        )  ## create dataset for raw data of each calibration peak
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "rawVerticalDetector", dtype="f", data=peakVerticalDetector
        )  ## create dataset for raw data of each calibration peak

        peaksGuessHD, peaksIndexHD = guessParameters(
            peakHorizontalDetector[:, 0],
            peakHorizontalDetector[:, 1] - backgroundHorizontalDetector,
            i,
            nbPeaksInBoxes,
        )  ## guess fit parameters for HD
        peaksGuessVD, peaksIndexVD = guessParameters(
            peakVerticalDetector[:, 0],
            peakVerticalDetector[:, 1] - backgroundVerticalDetector,
            i,
            nbPeaksInBoxes,
        )  ## guess fit parameters for VD
        yCalculatedBackgroundHD, coeffBgdHD = calcBackground(
            peakHorizontalDetector[:, 0],
            peakHorizontalDetector[:, 1],
            peaksGuessHD[-1],
            peaksGuessHD[2],
            i,
            nbPeaksInBoxes,
            peaksIndexHD,
        )  ## calculated ybackground of the horizontal detector
        yCalculatedBackgroundVD, coeffBgdVD = calcBackground(
            peakVerticalDetector[:, 0],
            peakVerticalDetector[:, 1],
            peaksGuessVD[-1],
            peaksGuessVD[2],
            i,
            nbPeaksInBoxes,
            peaksIndexVD,
        )  ## calculated ybackground of the vertical detector
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "backgroundHorizontalDetector",
            dtype="float64",
            data=np.transpose((peakHorizontalDetector[:, 0], yCalculatedBackgroundHD)),
        )  ## create dataset for background of each calibration peak for HD
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "backgroundVerticalDetector",
            dtype="float64",
            data=np.transpose((peakVerticalDetector[:, 0], yCalculatedBackgroundVD)),
        )  ## create dataset for background of each calibration peak for VD
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "bgdSubsDataHorizontalDetector",
            dtype="float64",
            data=np.transpose(
                (
                    peakHorizontalDetector[:, 0],
                    peakHorizontalDetector[:, 1] - yCalculatedBackgroundHD,
                )
            ),
        )  ## create dataset for HD raw data after subst of background
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "bgdSubsDataVerticalDetector",
            dtype="float64",
            data=np.transpose(
                (
                    peakVerticalDetector[:, 0],
                    peakVerticalDetector[:, 1] - yCalculatedBackgroundVD,
                )
            ),
        )  ## create dataset for VD raw data after subst of background
        initialGuessHD = np.zeros(5 * nbPeaksInBoxes[i])
        initialGuessVD = np.zeros(5 * nbPeaksInBoxes[i])
        for n in range(nbPeaksInBoxes[i]):
            initialGuessHD[5 * n] = peaksGuessHD[3 * n]
            initialGuessHD[5 * n + 1] = peaksGuessHD[3 * n + 1]
            initialGuessHD[5 * n + 2] = peaksGuessHD[3 * n + 2]
            initialGuessHD[5 * n + 3] = peaksGuessHD[3 * n + 2]
            initialGuessHD[5 * n + 4] = 0.5
            initialGuessVD[5 * n] = peaksGuessVD[3 * n]
            initialGuessVD[5 * n + 1] = peaksGuessVD[3 * n + 1]
            initialGuessVD[5 * n + 2] = peaksGuessVD[3 * n + 2]
            initialGuessVD[5 * n + 3] = peaksGuessVD[3 * n + 2]
            initialGuessVD[5 * n + 4] = 0.5
        optimal_parametersHD, covarianceHD = scipy.optimize.curve_fit(
            f=splitPseudoVoigt,
            xdata=peakHorizontalDetector[:, 0],
            ydata=peakHorizontalDetector[:, 1] - yCalculatedBackgroundHD,
            p0=initialGuessHD,
            sigma=None,
        )  ## fit of the peak of the Horizontal detector
        optimal_parametersVD, covarianceVD = scipy.optimize.curve_fit(
            f=splitPseudoVoigt,
            xdata=peakVerticalDetector[:, 0],
            ydata=peakVerticalDetector[:, 1] - yCalculatedBackgroundVD,
            p0=initialGuessVD,
            sigma=None,
        )  ## fit of the peak of the Vertical detector
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "fitHorizontalDetector",
            dtype="float64",
            data=np.transpose(
                (
                    peakHorizontalDetector[:, 0],
                    splitPseudoVoigt(peakHorizontalDetector[:, 0], optimal_parametersHD)
                    + yCalculatedBackgroundHD,
                )
            ),
        )  ## fitted data of the horizontal detector
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "fitVerticalDetector",
            dtype="float64",
            data=np.transpose(
                (
                    peakVerticalDetector[:, 0],
                    splitPseudoVoigt(peakVerticalDetector[:, 0], optimal_parametersVD)
                    + yCalculatedBackgroundVD,
                )
            ),
        )  ## fitted data of the vertical detector
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "errorHorizontalDetector",
            dtype="float64",
            data=np.transpose(
                (
                    peakHorizontalDetector[:, 0],
                    np.absolute(
                        splitPseudoVoigt(
                            peakHorizontalDetector[:, 0], optimal_parametersHD
                        )
                        + yCalculatedBackgroundHD
                        - peakHorizontalDetector[:, 1]
                    ),
                )
            ),
        )  ## error of the horizontal detector
        fitLevel1_2[f"fitLine_{str(i)}"].create_dataset(
            "errorVerticalDetector",
            dtype="float64",
            data=np.transpose(
                (
                    peakVerticalDetector[:, 0],
                    np.absolute(
                        splitPseudoVoigt(
                            peakVerticalDetector[:, 0], optimal_parametersVD
                        )
                        + yCalculatedBackgroundVD
                        - peakVerticalDetector[:, 1]
                    ),
                )
            ),
        )  ## error of the vertical detector
        for n in range(nbPeaksInBoxes[i]):
            fitParamsHD = np.append(
                fitParamsHD,
                np.append(
                    optimal_parametersHD[5 * n : 5 * n + 5],
                    100
                    * np.sum(
                        np.absolute(
                            splitPseudoVoigt(
                                peakHorizontalDetector[:, 0], optimal_parametersHD
                            )
                            + backgroundHorizontalDetector
                            - peakHorizontalDetector[:, 1]
                        )
                    )
                    / np.sum(peakHorizontalDetector[:, 1]),
                ),
                axis=0,
            )  ##
            fitParamsVD = np.append(
                fitParamsVD,
                np.append(
                    optimal_parametersVD[5 * n : 5 * n + 5],
                    100
                    * np.sum(
                        np.absolute(
                            splitPseudoVoigt(
                                peakVerticalDetector[:, 0], optimal_parametersVD
                            )
                            + backgroundVerticalDetector
                            - peakVerticalDetector[:, 1]
                        )
                    )
                    / np.sum(peakVerticalDetector[:, 1]),
                ),
                axis=0,
            )  ##
            uncertaintyFitParamsHD = np.append(
                uncertaintyFitParamsHD,
                np.sqrt(np.diag(covarianceHD))[5 * n : 5 * n + 5],
                axis=0,
            )  ##
            uncertaintyFitParamsVD = np.append(
                uncertaintyFitParamsVD,
                np.sqrt(np.diag(covarianceVD))[5 * n : 5 * n + 5],
                axis=0,
            )  ##
    rawDataLevel1_1.create_dataset(
        "horizontalDetector", dtype="float64", data=patternHorizontalDetector
    )  ## save raw data of the horizontal detector
    rawDataLevel1_1.create_dataset(
        "verticalDetector", dtype="float64", data=patternVerticalDetector
    )  ## save raw data of the vertical detector
    fitLevel1_2["fitParams"].create_dataset(
        "fitParamsHD",
        dtype="float64",
        data=np.reshape(fitParamsHD, (int(np.size(fitParamsHD) / 6), 6)),
    )  ## save parameters of the fit of HD
    fitLevel1_2["fitParams"].create_dataset(
        "fitParamsVD",
        dtype="float64",
        data=np.reshape(fitParamsVD, (int(np.size(fitParamsVD) / 6), 6)),
    )  ## save parameters of the fit of VD
    fitLevel1_2["fitParams"].create_dataset(
        "uncertaintyFitParamsHD",
        dtype="float64",
        data=np.reshape(
            uncertaintyFitParamsHD, (int(np.size(uncertaintyFitParamsHD) / 5), 5)
        ),
    )  ## save uncertainty on the parameters of the fit of HD
    fitLevel1_2["fitParams"].create_dataset(
        "uncertaintyFitParamsVD",
        dtype="float64",
        data=np.reshape(
            uncertaintyFitParamsVD, (int(np.size(uncertaintyFitParamsVD) / 5), 5)
        ),
    )  ## save uncertainty on the parameters of the fit of VD

    with h5py.File(
        pathFileDetectorCalibration, "r"
    ) as h5pFDC:  ## Read the h5 file of the energy calibration of the two detectors
        calibCoeffsHD = h5pFDC[
            f"detectorCalibration/{scanDetectorCalibration}/calibCoeffs/calibCoeffsHD"
        ][
            ()
        ]  ## import the energy calibration coefficients of the horizontal detector
        calibCoeffsVD = h5pFDC[
            f"detectorCalibration/{scanDetectorCalibration}/calibCoeffs/calibCoeffsVD"
        ][
            ()
        ]  ## import the energy calibration coefficients of the vertical detector
        uncertaintyCalibCoeffsHD = h5pFDC[
            f"detectorCalibration/{scanDetectorCalibration}/calibCoeffs/uncertaintyCalibCoeffsHD"
        ][
            ()
        ]  ## import the uncertainty of the energy calibration coefficients of the horizontal detector
        uncertaintyCalibCoeffsVD = h5pFDC[
            f"detectorCalibration/{scanDetectorCalibration}/calibCoeffs/uncertaintyCalibCoeffsVD"
        ][
            ()
        ]  ## import the uncertainty of the energy calibration coefficients of the vertical detector
    calibrantSample = np.loadtxt(
        sampleCalibrantFile
    )  ## open source calibration text file
    conversionChannelEnergyHD = np.polyval(
        calibCoeffsHD, fitLevel1_2["fitParams/fitParamsHD"][:, 1]
    )  ## conversion of the channel to energy for the horizontal detector
    conversionChannelEnergyVD = np.polyval(
        calibCoeffsVD, fitLevel1_2["fitParams/fitParamsVD"][:, 1]
    )  ## conversion of the channel to energy for the vertical detector
    curveAngleCalibrationHD[:, 0] = 1 / calibrantSample[: np.sum(nbPeaksInBoxes)]
    curveAngleCalibrationHD[:, 1] = conversionChannelEnergyHD
    fitLevel1_2["curveAngleCalibration"].create_dataset(
        "curveAngleCalibrationHD", dtype="float64", data=curveAngleCalibrationHD
    )  ## save curve energy VS 1/d for horizontal detector (d = hkl interriticular distance of the calibrant sample)
    curveAngleCalibrationVD[:, 0] = 1 / calibrantSample[: np.sum(nbPeaksInBoxes)]
    curveAngleCalibrationVD[:, 1] = conversionChannelEnergyVD
    fitLevel1_2["curveAngleCalibration"].create_dataset(
        "curveAngleCalibrationVD", dtype="float64", data=curveAngleCalibrationVD
    )  ## save curve energy VS 1/d for vertical detector (d = hkl interriticular distance of the calibrant sample)

    calibratedAngleHD, covCalibratedAngleHD = scipy.optimize.curve_fit(
        f=linefunc,
        xdata=curveAngleCalibrationHD[:, 0],
        ydata=curveAngleCalibrationHD[:, 1],
        p0=np.polyfit(
            x=curveAngleCalibrationHD[:, 0], y=curveAngleCalibrationHD[:, 1], deg=1
        )[0],
        sigma=uChEConversion(
            calibCoeffsHD[0],
            calibCoeffsHD[1],
            calibCoeffsHD[2],
            fitLevel1_2["fitParams/fitParamsHD"][:, 1],
            uncertaintyCalibCoeffsHD[0],
            uncertaintyCalibCoeffsHD[1],
            uncertaintyCalibCoeffsHD[2],
            fitLevel1_2["fitParams/uncertaintyFitParamsHD"][:, 1],
        ),
    )  ## calculation of 12.398/2*sin(theta) of the diffraction angle of the horizontal detector
    calibratedAngleVD, covCalibratedAngleVD = scipy.optimize.curve_fit(
        f=linefunc,
        xdata=curveAngleCalibrationVD[:, 0],
        ydata=curveAngleCalibrationVD[:, 1],
        p0=np.polyfit(
            x=curveAngleCalibrationVD[:, 0], y=curveAngleCalibrationVD[:, 1], deg=1
        )[0],
        sigma=uChEConversion(
            calibCoeffsVD[0],
            calibCoeffsVD[1],
            calibCoeffsVD[2],
            fitLevel1_2["fitParams/fitParamsHD"][:, 1],
            uncertaintyCalibCoeffsVD[0],
            uncertaintyCalibCoeffsVD[1],
            uncertaintyCalibCoeffsVD[2],
            fitLevel1_2["fitParams/uncertaintyFitParamsVD"][:, 1],
        ),
    )  ## calculation of 12.398/2*sin(theta) of the diffraction angle of the vertical detector
    # print(calibratedAngleHD)
    # print(calibratedAngleVD)
    fitLevel1_2["calibratedAngle"].create_dataset(
        "calibratedAngleHD",
        dtype="float64",
        data=np.rad2deg(2 * np.arcsin(12.398 / (2 * calibratedAngleHD))),
    )  ## save the calibrated diffraction angle in degree of the horizontal detector
    fitLevel1_2["calibratedAngle"].create_dataset(
        "calibratedAngleVD",
        dtype="float64",
        data=np.rad2deg(2 * np.arcsin(12.398 / (2 * calibratedAngleVD))),
    )  ## save the calibrated diffraction angle in degree of the vertical detector
    fitLevel1_2["calibratedAngle"].create_dataset(
        "uncertaintyCalibratedAngleHD",
        dtype="float64",
        data=np.sqrt(np.diag(covCalibratedAngleHD)),
    )  ## save the uncertainty of the calibrated diffraction angle in degree of the horizontal detector
    fitLevel1_2["calibratedAngle"].create_dataset(
        "uncertaintyCalibratedAngleVD",
        dtype="float64",
        data=np.sqrt(np.diag(covCalibratedAngleVD)),
    )  ## save the uncertainty of the calibrated diffraction angle in degree of the vertical detector
    fitLevel1_2["curveAngleCalibration"].create_dataset(
        "fitCurveAngleCalibrationHD",
        dtype="float64",
        data=np.transpose(
            (
                curveAngleCalibrationHD[:, 0],
                calibratedAngleHD * curveAngleCalibrationHD[:, 0],
            )
        ),
    )  ## save curve energy VS 1/d for horizontal detector calculated using the fitted value 12.398/2*sin(theta)
    fitLevel1_2["curveAngleCalibration"].create_dataset(
        "fitCurveAngleCalibrationVD",
        dtype="float64",
        data=np.transpose(
            (
                curveAngleCalibrationVD[:, 0],
                calibratedAngleVD * curveAngleCalibrationVD[:, 0],
            )
        ),
    )  ## save curve energy VS 1/d for vertical detector calculated using the fitted value 12.398/2*sin(theta)
    fitLevel1_2["curveAngleCalibration"].create_dataset(
        "errorCurveAngleCalibrationHD",
        dtype="float64",
        data=np.transpose(
            (
                curveAngleCalibrationHD[:, 0],
                np.abs(
                    curveAngleCalibrationHD[:, 1]
                    - (calibratedAngleHD * curveAngleCalibrationHD[:, 0])
                ),
            )
        ),
    )  ## error between the fitted (calculated using the fitted value 12.398/2*sin(theta)) and experimental curve of energy VS 1/d for horizontal detector
    fitLevel1_2["curveAngleCalibration"].create_dataset(
        "errorCurveAngleCalibrationVD",
        dtype="float64",
        data=np.transpose(
            (
                curveAngleCalibrationVD[:, 0],
                np.abs(
                    curveAngleCalibrationVD[:, 1]
                    - (calibratedAngleVD * curveAngleCalibrationVD[:, 0])
                ),
            )
        ),
    )  ## error between the fitted (calculated using the fitted value 12.398/2*sin(theta)) and experimental curve of energy VS 1/d for vertical detector

    infoGroup.create_dataset(
        "pathDetectorCalibrationParams",
        dtype=h5py.string_dtype(encoding="utf-8"),
        data=pathFileDetectorCalibration
        + "/"
        + f"detectorCalibration/{scanDetectorCalibration}/calibCoeffs",
    )  ## save of the path of the file containing the energy calibration coefficient for the two detectors used for the conversion of channels ====> energy in the info group

    h5Save.close()
    return
