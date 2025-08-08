#include "task_handler.h"
#include <cstdio>
#include <ctime>
#include <vector>
#include <map>
#include <iostream>
#include <string>

using namespace std;

// ******************************************************************************
// *                                                                            *
// *          Main driver program to run "SigMonD" in batch mode                *
// *                                                                            *
// *   Program takes a single argument that is the name of the input file.      *
// *   Input file must contain a single XML document with root tag named        *
// *   <SigMonD>.  The input XML must have the form below:                      *
// *                                                                            *
// *    <SigMonD>                                                               *
// *                                                                            *
// *       <Initialize>                                                         *
// *         <ProjectName>NameOfProject</ProjectName>                           * 
// *         <Logfile>output.log</Logfile>                                      *
// *         <KnownEnsemblesFile>/path/ensembles.xml</KnownEnsemblesFile> (optional)  *
// *         <EchoXML/>                                                         *
// *         <MCBinsInfo>  ...  </MCBinsInfo>                                   *
// *         <MCSamplingInfo> ... </MCSamplingInfo>                             *
// *         <MCObservables>  ...  </MCObservables>                             *
// *       </Initialize>                                                        *
// *                                                                            *
// *       <TaskSequence>                                                       *
// *         <Task><Action>...</Action> ...  </Task>                            *
// *         <Task><Action>...</Action> ...  </Task>                            *
// *           ....                                                             *
// *       </TaskSequence>                                                      *
// *                                                                            *
// *    </SigMonD>                                                              *
// *                                                                            *
// *                                                                            *
// *   (a) If <ProjectName> is missing, a default name will be created.         *
// *                                                                            *
// *   (b) If <Logfile> is missing, a default name for the log file is used.    *
// *                                                                            *
// *   (c) If <EchoXML> is missing, the input XML will not be written to the    *
// *       log file.                                                            *
// *                                                                            *
// *   (d) Various ensembles are made known to SigMonD in the ensembles XML     *
// *       file.  The absolute path to this file can be specified in            *
// *       the <KnownEnsemblesFile> tag.  If not given, a default location      *
// *       for this file has been stored during the compilation.                *
// *       This file must have information specified in the following XML       *
// *       format:                                                              *
// *                                                                            *
// *      <KnownEnsembles>                                                      *
// *        <Infos>                                                             *
// *          <EnsembleInfo>...</EnsembleInfo>                                  *
// *          <EnsembleInfo>...</EnsembleInfo>                                  *
// *           ....                                                             *
// *        </Infos>                                                            *
// *        <CLSEnsembleWeights>                                                *
// *          <Ensemble>...</Ensemble>                                          *
// *           ....                                                             *
// *        </CLSEnsembleWeights>                                               *
// *      </KnownEnsembles>                                                     *
// *                                                                            *
// *       with each ensemble in the <Infos> tags specified by                  *
// *                                                                            *
// *      <EnsembleInfo>                                                        *
// *         <Id>clover_s24_t128_ud840_s743</Id>                                *
// *         <NStreams>4</NStreams>                                             *
// *         <NMeas>551</NMeas>                                                 *
// *         <NSpace>24</NSpace>                                                *
// *         <NTime>128</NTime>                                                 *
// *         <Weighted/>  (if has CLS weights; omit otherwise)                  *
// *      </EnsembleInfo>                                                       *
// *                                                                            *
// *       The entries in the <CLSEnsembleWeights> tag must have the form:      *
// *                                                                            *
// *      <Ensemble>                                                            *
// *         <Id>cls21_D200_r000</Id>                                           *
// *         <Weights> 0.999 0.998 ... </Weights>                               *
// *      </Ensemble>                                                           *
// *                                                                            *
// *   (e) The tag <MCBinsInfo> is mandatory: it specifies the ensemble,        *
// *       controls rebinning the data, and possibly omitting certain           *
// *       configurations in the ensemble.  The XML must have the form below:   *
// *                                                                            *
// *      <MCBinsInfo>                                                          *
// *        <MCEnsembleInfo>clover_s24_t128_ud840_s743</MCEnsembleInfo>         *
// *        <TweakEnsemble>  (optional)                                         *
// *           <Rebin>2</Rebin>                                                 *
// *           <Omissions>2 7 11</Omissions>                                    *
// *        </TweakEnsemble>                                                    *
// *      </MCBinsInfo>                                                         *
// *                                                                            *
// *       Note that when reading from bin files (other than basic LapH files), *
// *       the omissions in the bin files MUST be the same as specified         *
// *       in <MCBinsInfo>.  The rebin value need NOT be the same.  The         *
// *       <Rebin> value must be an integer multiple of the rebin factors       *
// *       in the bin files.                                                    *
// *                                                                            *
// *   (f) The tag <MCSamplingInfo> is mandatory.  It controls the default      *
// *       resampling method:  jackknife or bootstrap.  This default method     *
// *       is assumed for all reading and writing sampling results to and       *
// *       from files.  Note that both jackknife and bootstrap resampling       *
// *       can be done in any program execution, but only one can be used       *
// *       for reading/writing to files.  This tag has the form below.  See     *
// *       comments for the MCSamplingInfo and Bootstrapper classes for more    *
// *       details about this tag.                                              *
// *                                                                            *
// *      <MCSamplingInfo>                                                      *
// *         <Jackknife/>                                                       *
// *      </MCSamplingInfo>                                                     *
// *                       OR                                                   *
// *      <MCSamplingInfo>                                                      *
// *         <Bootstrapper>                                                     *
// *            <NumberResamplings>2048</NumberResamplings>                     *
// *            <Seed>6754</Seed>                                               *
// *            <BootSkip>127</BootSkip>                                        *
// *            <Precompute/>  (optional)                                       *
// *         </Bootstrapper>                                                    *
// *      </MCSamplingInfo>                                                     *
// *                                                                            *
// *   (g) <MCObservables> describes the data to be input for analysis. See     *
// *       class "MCObsGetHandler" in "source/data_handling/obs_get_handler.h"  *
// *       for a description of the XML needed in this tag.  This handles       *
// *       input of only "standard" observables (see "mcobs_info.h").           *
// *       Only data for standard observables can be read through this tag.     *
// *       Data of "nonstandard" form, such as fit parameters, rotated          *
// *       correlators, and other user-defined observables, must be read        *
// *       from file in a <Task> tag.                                           *
// *                                                                            *
// *   (h) The <Task> tags are needed in "batch" mode, but can be omitted in    *
// *   "cli" or "gui".  Each <Task> tag must begin with an <Action> tag.        *
// *   The <Action> tag must be a string in the "m_task_map".  The remaining    *
// *   XML depends on the action being taken.                                   *
// *                                                                            *
// *                                                                            *
// ******************************************************************************

void show_help() {
    cout << "SigMonD - Signal Extraction from Monte Carlo Data" << endl;
    cout << "A software suite for the analysis of Monte Carlo data in lattice QCD" << endl << endl;
    
    cout << "USAGE:" << endl;
    cout << "  sigmond_batch <input_file.xml>" << endl;
    cout << "  sigmond_batch -h|--help" << endl << endl;
    
    cout << "DESCRIPTION:" << endl;
    cout << "  Main driver program to run SigMonD in batch mode." << endl;
    cout << "  Program takes a single argument that is the name of the input file." << endl;
    cout << "  Input file must contain a single XML document with root tag named <SigMonD>." << endl << endl;
    
    cout << "INPUT XML FORMAT:" << endl;
    cout << "  The input XML must have the form below:" << endl << endl;
    cout << "    <SigMonD>" << endl;
    cout << "      <Initialize>" << endl;
    cout << "        <ProjectName>NameOfProject</ProjectName>" << endl;
    cout << "        <Logfile>output.log</Logfile>" << endl;
    cout << "        <KnownEnsemblesFile>/path/ensembles.xml</KnownEnsemblesFile> (optional)" << endl;
    cout << "        <EchoXML/>" << endl;
    cout << "        <MCBinsInfo>  ...  </MCBinsInfo>" << endl;
    cout << "        <MCSamplingInfo> ... </MCSamplingInfo>" << endl;
    cout << "        <MCObservables>  ...  </MCObservables>" << endl;
    cout << "      </Initialize>" << endl;
    cout << "      <TaskSequence>" << endl;
    cout << "        <Task><Action>...</Action> ...  </Task>" << endl;
    cout << "        <Task><Action>...</Action> ...  </Task>" << endl;
    cout << "          ...." << endl;
    cout << "      </TaskSequence>" << endl;
    cout << "    </SigMonD>" << endl << endl;
    
    cout << "INITIALIZATION TAGS:" << endl;
    cout << "  (a) If <ProjectName> is missing, a default name will be created." << endl;
    cout << "  (b) If <Logfile> is missing, a default name for the log file is used." << endl;
    cout << "  (c) If <EchoXML> is missing, the input XML will not be written to the log file." << endl;
    cout << "  (d) Various ensembles are made known to SigMonD in the ensembles XML file." << endl;
    cout << "      The absolute path to this file can be specified in the <KnownEnsemblesFile> tag." << endl;
    cout << "      If not given, a default location for this file has been stored during compilation." << endl << endl;
    
    cout << "ENSEMBLES XML FORMAT:" << endl;
    cout << "  This file must have information specified in the following XML format:" << endl << endl;
    cout << "    <KnownEnsembles>" << endl;
    cout << "      <Infos>" << endl;
    cout << "        <EnsembleInfo>...</EnsembleInfo>" << endl;
    cout << "        <EnsembleInfo>...</EnsembleInfo>" << endl;
    cout << "         ...." << endl;
    cout << "      </Infos>" << endl;
    cout << "      <CLSEnsembleWeights>" << endl;
    cout << "        <Ensemble>...</Ensemble>" << endl;
    cout << "         ...." << endl;
    cout << "      </CLSEnsembleWeights>" << endl;
    cout << "    </KnownEnsembles>" << endl << endl;
    
    cout << "  with each ensemble in the <Infos> tags specified by:" << endl << endl;
    cout << "    <EnsembleInfo>" << endl;
    cout << "      <Id>clover_s24_t128_ud840_s743</Id>" << endl;
    cout << "      <NStreams>4</NStreams>" << endl;
    cout << "      <NMeas>551</NMeas>" << endl;
    cout << "      <NSpace>24</NSpace>" << endl;
    cout << "      <NTime>128</NTime>" << endl;
    cout << "      <Weighted/>  (if has CLS weights; omit otherwise)" << endl;
    cout << "    </EnsembleInfo>" << endl << endl;
    
    cout << "  The entries in the <CLSEnsembleWeights> tag must have the form:" << endl << endl;
    cout << "    <Ensemble>" << endl;
    cout << "      <Id>cls21_D200_r000</Id>" << endl;
    cout << "      <Weights> 0.999 0.998 ... </Weights>" << endl;
    cout << "    </Ensemble>" << endl << endl;
    
    cout << "MCBINSINFO TAG:" << endl;
    cout << "  The tag <MCBinsInfo> is mandatory: it specifies the ensemble, controls rebinning" << endl;
    cout << "  the data, and possibly omitting certain configurations in the ensemble." << endl;
    cout << "  The XML must have the form below:" << endl << endl;
    cout << "    <MCBinsInfo>" << endl;
    cout << "      <MCEnsembleInfo>clover_s24_t128_ud840_s743</MCEnsembleInfo>" << endl;
    cout << "      <TweakEnsemble>  (optional)" << endl;
    cout << "         <Rebin>2</Rebin>" << endl;
    cout << "         <Omissions>2 7 11</Omissions>" << endl;
    cout << "      </TweakEnsemble>" << endl;
    cout << "    </MCBinsInfo>" << endl << endl;
    
    cout << "  Note that when reading from bin files (other than basic LapH files), the omissions" << endl;
    cout << "  in the bin files MUST be the same as specified in <MCBinsInfo>. The rebin value" << endl;
    cout << "  need NOT be the same. The <Rebin> value must be an integer multiple of the rebin" << endl;
    cout << "  factors in the bin files." << endl << endl;
    
    cout << "MCSAMPLINGINFO TAG:" << endl;
    cout << "  The tag <MCSamplingInfo> is mandatory. It controls the default resampling method:" << endl;
    cout << "  jackknife or bootstrap. This default method is assumed for all reading and writing" << endl;
    cout << "  sampling results to and from files. Note that both jackknife and bootstrap resampling" << endl;
    cout << "  can be done in any program execution, but only one can be used for reading/writing" << endl;
    cout << "  to files. This tag has the form below:" << endl << endl;
    cout << "    <MCSamplingInfo>" << endl;
    cout << "      <Jackknife/>" << endl;
    cout << "    </MCSamplingInfo>" << endl;
    cout << "                     OR" << endl;
    cout << "    <MCSamplingInfo>" << endl;
    cout << "      <Bootstrapper>" << endl;
    cout << "         <NumberResamplings>2048</NumberResamplings>" << endl;
    cout << "         <Seed>6754</Seed>" << endl;
    cout << "         <BootSkip>127</BootSkip>" << endl;
    cout << "         <Precompute/>  (optional)" << endl;
    cout << "      </Bootstrapper>" << endl;
    cout << "    </MCSamplingInfo>" << endl << endl;
    
    cout << "MCOBSERVABLES TAG:" << endl;
    cout << "  <MCObservables> describes the data to be input for analysis. See class \"MCObsGetHandler\"" << endl;
    cout << "  in \"source/data_handling/obs_get_handler.h\" for a description of the XML needed" << endl;
    cout << "  in this tag. This handles input of only \"standard\" observables (see \"mcobs_info.h\")." << endl;
    cout << "  Only data for standard observables can be read through this tag. Data of \"nonstandard\"" << endl;
    cout << "  form, such as fit parameters, rotated correlators, and other user-defined observables," << endl;
    cout << "  must be read from file in a <Task> tag." << endl << endl;
    
    cout << "TASK TAGS:" << endl;
    cout << "  The <Task> tags are needed in \"batch\" mode, but can be omitted in \"cli\" or \"gui\"." << endl;
    cout << "  Each <Task> tag must begin with an <Action> tag. The <Action> tag must be a string" << endl;
    cout << "  in the \"m_task_map\". The remaining XML depends on the action being taken." << endl << endl;
    
    cout << "OPTIONS:" << endl;
    cout << "  -h, --help    Show this help message and exit" << endl << endl;
    
    cout << "EXAMPLES:" << endl;
    cout << "  sigmond_batch analysis_input.xml" << endl;
    cout << "  sigmond_batch /path/to/input/file.xml" << endl << endl;
}


int main(int argc, const char* argv[])
{

 if ((sizeof(int)!=4)||(sizeof(unsigned int)!=4)){
    cout << "Fatal: size of int on this architecture is not 4!"<<endl;
    return 1;}

     // convert arguments to C++ strings
 vector<string> tokens(argc-1);
 for (int k=1;k<argc;++k){
    tokens[k-1]=string(argv[k]);}

 // Handle help options first
 if (tokens.size()==1 && (tokens[0]=="-h" || tokens[0]=="--help")){
    show_help();
    return 0;}

 if (tokens.size()!=1){
    cout << "Error: batch mode requires a file name as the only argument"<<endl;
    cout << "Use 'sigmond_batch --help' for usage information."<<endl;
    return 1;}

 try{
    XMLHandler xmltask;  
    xmltask.set_exceptions_on();
    if (tokens.size()>0){
       string filename(tokens[0]);
       xmltask.set_from_file(filename);}

        // set up the task handler
    TaskHandler tasker(xmltask);

        // do the tasks in sequence
    tasker.do_batch_tasks(xmltask);
    }
 catch(const std::exception& msg){
    cout << "Error: "<<msg.what()<<endl;
    return 1;}

 return 0;
}

