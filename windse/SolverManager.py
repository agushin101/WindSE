"""
The SolverManager contains all the different ways to solve problems generated
in windse
"""

import __main__
import os

### Get the name of program importing this package ###
main_file = os.path.basename(__main__.__file__)

### This checks if we are just doing documentation ###
if main_file != "sphinx-build":
    from dolfin import *
    from sys import platform
    import time
    import numpy as np

    ### Import the cumulative parameters ###
    from windse import windse_parameters

    ### Check if we need dolfin_adjoint ###
    if windse_parameters["general"].get("dolfin_adjoint", False):
        from dolfin_adjoint import *

    ### This import improves the plotter functionality on Mac ###
    if platform == 'darwin':
        import matplotlib
        matplotlib.use('TKAgg')
    import matplotlib.pyplot as plt

    ### Improve Solver parameters ###
    parameters["std_out_all_processes"] = False;
    parameters['form_compiler']['cpp_optimize_flags'] = '-O3 -fno-math-errno -march=native'        
    parameters["form_compiler"]["optimize"]     = True
    parameters["form_compiler"]["cpp_optimize"] = True
    parameters['form_compiler']['representation'] = 'uflacs'
    parameters['form_compiler']['quadrature_degree'] = 6

class GenericSolver(object):
    """
    A GenericSolver contains on the basic functions required by all solver objects.
    """
    def __init__(self,problem):
        self.params = windse_parameters
        self.problem  = problem
        # self.u_next,self.p_next = self.problem.up_next.split(True)
        self.u_next,self.p_next = split(self.problem.up_next)
        self.nu_T = self.problem.nu_T
        self.first_save = True
        self.fprint = self.params.fprint


    def Plot(self):
        """
        This function plots the solution functions using matplotlib and saves the 
        output to output/.../plots/u.pdf and output/.../plots/p.pdf
        """

        ### Create the path names ###
        folder_string = self.params.folder+"/plots/"
        u_string = self.params.folder+"/plots/u.pdf"
        p_string = self.params.folder+"/plots/p.pdf"

        ### Check if folder exists ###
        if not os.path.exists(folder_string): os.makedirs(folder_string)

        ### Plot the x component of velocity ###
        plot(self.u_next[0],title="Velocity in the x Direction")
        plt.savefig(u_string)
        plt.figure()

        ### Plot the pressure ###
        plot(self.p_next,title="Pressure")
        plt.savefig(p_string)
        plt.show()

    def Save(self,val=0):
        """
        This function saves the mesh and boundary markers to output/.../solutions/
        """
        u,p = self.problem.up_next.split(True,annotate=False)
        if self.first_save:
            self.u_file = self.params.Save(u,"velocity",subfolder="solutions/",val=val)
            self.p_file = self.params.Save(p,"pressure",subfolder="solutions/",val=val)
            # self.nuT_file = self.params.Save(self.nu_T,"eddy_viscosity",subfolder="solutions/",val=val)
            self.first_save = False
        else:
            self.params.Save(u,"velocity",subfolder="solutions/",val=val,file=self.u_file)
            self.params.Save(p,"pressure",subfolder="solutions/",val=val,file=self.p_file)
            # self.params.Save(self.nu_T,"eddy_viscosity",subfolder="solutions/",val=val,file=self.nuT_file)

    def ChangeWindAngle(self,theta):
        """
        This function recomputes all necessary components for a new wind direction

        Args: 
            theta (float): The new wind angle in radians
        """
        self.problem.ChangeWindAngle(theta)
        
class SteadySolver(GenericSolver):
    """
    This solver is for solving the steady state problem

    Args: 
        problem (:meth:`windse.ProblemManager.GenericProblem`): a windse problem object.
    """
    def __init__(self,problem):
        super(SteadySolver, self).__init__(problem)

    def Solve(self,iter_val=0):
        """
        This solves the problem setup by the problem object.
        """

        ### Save Files before solve ###
        self.fprint("Saving Input Data",special="header")
        if "mesh" in self.params.output:
            self.problem.dom.Save(val=iter_val)
        if "initial_guess" in self.params.output:
            self.problem.bd.SaveInitialGuess(val=iter_val)
        if "height" in self.params.output and self.problem.dom.dim == 3:
            self.problem.bd.SaveHeight()
        if "turbine_force" in self.params.output:
            self.problem.farm.SaveTurbineForce(val=iter_val)
        self.fprint("Finished",special="footer")

        ####################################################################
        ### This is the better way to define a nonlinear problem but it 
        ### doesn't play nice with dolfin_adjoint
        # ### Define Jacobian ###
        # dU = TrialFunction(self.problem.fs.W)
        # J  = derivative(self.problem.F,  self.problem.up_next, dU)

        # ### Setup nonlinear solver ###
        # nonlinear_problem = NonlinearVariationalProblem(self.problem.F, self.problem.up_next, self.problem.bd.bcs, J)
        # nonlinear_solver  = NonlinearVariationalSolver(nonlinear_problem)

        # ### Set some parameters ###
        # solver_parameters = nonlinear_solver.parameters
        # solver_parameters["nonlinear_solver"] = "snes"
        # solver_parameters["snes_solver"]["linear_solver"] = "mumps"
        # solver_parameters["snes_solver"]["maximum_iterations"] = 50
        # solver_parameters["snes_solver"]["error_on_nonconvergence"] = False
        # solver_parameters["snes_solver"]["line_search"] = "bt" # Available: basic, bt, cp, l2, nleqerr

        ### Solve the problem ###
        # self.fprint("Solving",special="header")
        # start = time.time()
        # iters, converged = nonlinear_solver.solve()
        # stop = time.time()
        # self.fprint("Total Nonlinear Iterations: {:d}".format(iters))
        # self.fprint("Converged Successfully: {0}".format(converged))
        ####################################################################


        # ### Add some helper functions to solver options ###
        solver_parameters = {"nonlinear_solver": "snes",
                             "snes_solver": {
                             "linear_solver": "mumps", 
                             "maximum_iterations": 40,
                             "error_on_nonconvergence": False,
                             "line_search": "bt",
                             }}

        ### Start the Solve Process ###
        self.fprint("Solving",special="header")
        start = time.time()
        
        # ### Solve the Baseline Problem ###
        # solve(self.problem.F_sans_tf == 0, self.problem.up_next, self.problem.bd.bcs, solver_parameters=solver_parameters, annotate=False)

        # ### Store the Baseline and Assign for the real solve ###
        # self.up_baseline = self.problem.up_next.copy(deepcopy=True)
        # self.problem.up_next.assign(self.up_baseline)

        ### Solve the real problem ###
        solve(self.problem.F == 0, self.problem.up_next, self.problem.bd.bcs, solver_parameters=solver_parameters)
        stop = time.time()
        self.fprint("Solve Complete: {:1.2f} s".format(stop-start),special="footer")
        # self.u_next,self.p_next = self.problem.up_next.split(True)
        self.u_next,self.p_next = split(self.problem.up_next)
        # self.nu_T = project(self.problem.nu_T,self.problem.fs.Q,annotate=False,solver_type='mumps')
        self.nu_T = None


        ### Save solutions ###
        if "solution" in self.params.output:
            self.fprint("Saving Solution",special="header")
            self.Save(val=iter_val)
            self.fprint("Finished",special="footer")

class MultiAngleSolver(SteadySolver):
    """
    This solver will solve the problem using the steady state solver for every
    angle in angles.

    Args: 
        problem (:meth:`windse.ProblemManager.GenericProblem`): a windse problem object.
        angles (list): A list of wind inflow directions.
    """ 

    def __init__(self,problem):
        super(MultiAngleSolver, self).__init__(problem)
        # if self.params["domain"]["type"] not in ["circle","cylinder","interpolated"]:
        #     raise ValueError("A circle, cylinder, or interpolated cylinder domain is required for a Multi-Angle Solver")
        self.orignal_solve = super(MultiAngleSolver, self).Solve
        self.wind_range = self.params["solver"].get("wind_range", None)
        if  self.wind_range is None:
            self.wind_range = [0, 2.0*np.pi]
            self.endpoint = self.params["solver"].get("endpoint", False)
        else:
            self.endpoint = self.params["solver"].get("endpoint", True)

        self.num_wind = self.params["solver"]["num_wind_angles"]
        self.angles = np.linspace(*self.wind_range,self.num_wind,endpoint=self.endpoint)

        #Check if we are optimizing
        if self.params.get("optimization",{}):
            self.optimizing = True
            self.J = 0
        else:
            self.optimizing = False

    def Solve(self):
        for i, theta in enumerate(self.angles):
            self.fprint("Performing Solve {:d} of {:d}".format(i+1,len(self.angles)),special="header")
            self.fprint("Wind Angle: "+repr(theta))
            if i > 0 or not near(theta,self.wind_range[0]):
                self.ChangeWindAngle(theta)
            self.orignal_solve(iter_val=theta)

            if self.optimizing:
                # self.J += assemble(-dot(self.problem.tf,self.u_next)*dx)
                # if self.problem.farm.yaw[0]**2 > 1e-4:
                #     self.J += assemble(-dot(self.problem.tf,self.u_next),*dx)
                # else:
                # self.J += assemble(-inner(dot(self.problem.tf,self.u_next),self.u_next[0]**2+self.u_next[1]**2)*dx)
                self.J += -self.CalculatePowerFunctional((theta-self.problem.dom.init_wind)) 
                # print(self.J)
            self.fprint("Finished Solve {:d} of {:d}".format(i+1,len(self.angles)),special="footer")

    def CalculatePowerFunctional(self,delta_yaw):
        self.fprint("Computing Power Functional")

        x=SpatialCoordinate(self.problem.dom.mesh)
        J=0.
        for i in range(self.problem.farm.numturbs):

            mx = self.problem.farm.mx[i]
            my = self.problem.farm.my[i]
            mz = self.problem.farm.mz[i]
            x0 = [mx,my,mz]
            W = self.problem.farm.W[i]*1.0
            R = self.problem.farm.RD[i]/2.0 
            ma = self.problem.farm.ma[i]
            yaw = self.problem.farm.myaw[i]+delta_yaw
            u = self.u_next

            WTGbase = Expression(("cos(yaw)","sin(yaw)","0.0"),yaw=float(yaw),degree=1)

            ### Rotate and Shift the Turbine ###
            xs = self.problem.farm.YawTurbine(x,x0,yaw)

            ### Create the function that represents the Thickness of the turbine ###
            T = exp(-pow((xs[0]/W),6.0))#/(T_norm*W)

            ### Create the function that represents the Disk of the turbine
            D = exp(-pow((pow((xs[1]/R),2)+pow((xs[2]/R),2)),6.0))#/(D_norm*R**2.0)

            u_d = u[0]*cos(yaw) + u[1]*sin(yaw)

            J += dot(T*D*WTGbase*u_d**2.0,u)*dx
        return J