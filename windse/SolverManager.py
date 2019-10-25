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
        self.u_next,self.p_next = self.problem.up_next.split(True)
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
        if self.first_save:
            self.u_file = self.params.Save(self.u_next,"velocity",subfolder="solutions/",val=val)
            self.p_file = self.params.Save(self.p_next,"pressure",subfolder="solutions/",val=val)
            self.nuT_file = self.params.Save(self.nu_T,"eddy_viscosity",subfolder="solutions/",val=val)
            self.first_save = False
        else:
            self.params.Save(self.u_next,"velocity",subfolder="solutions/",val=val,file=self.u_file)
            self.params.Save(self.p_next,"pressure",subfolder="solutions/",val=val,file=self.p_file)
            self.params.Save(self.nu_T,"eddy_viscosity",subfolder="solutions/",val=val,file=self.nuT_file)

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
                             "maximum_iterations": 50,
                             "error_on_nonconvergence": False,
                             "line_search": "bt"
                             }}

        ### Solve the problem ###
        self.fprint("Solving",special="header")
        start = time.time()
        solve(self.problem.F == 0, self.problem.up_next, self.problem.bd.bcs, solver_parameters=solver_parameters)
        stop = time.time()
        self.fprint("Solve Complete: {:1.2f} s".format(stop-start),special="footer")
        self.u_next,self.p_next = self.problem.up_next.split(True)
        self.nu_T = project(self.problem.nu_T,self.problem.fs.Q)

        ### Save solutions ###
        if "solution" in self.params.output:
            self.fprint("Saving Solution",special="header")
            self.Save(val=iter_val)
            self.fprint("Finished",special="footer")

# ================================================================

class UnsteadySolver(GenericSolver):
    """
    This solver is for solving an unsteady problem.  As such, it contains
    additional time-stepping features and functions not present in other solvers.
    This solver can only be used if an unsteady problem has been specified in
    the input file.

    Args: 
        problem (:meth:`windse.ProblemManager.GenericProblem`): a windse problem object.
    """
    def __init__(self,problem):
        super(UnsteadySolver, self).__init__(problem)

    # ================================================================

    def Solve(self,iter_val=0):
        # Start the unsteady solver ONLY if an unsteady problem has been created
        if self.problem.params["problem"]["type"] == 'unsteady':
            self.fprint("Solving with UnsteadySolver", special="header")
        else:
            raise ValueError("UnsteadySolver can only be run with ProblemType = unsteady, not %s" \
                % (self.problem.params["problem"]["type"]))

        # ================================================================

        # Define the final simulation time
        # FIXME: This should also be set in params.yaml input file
        # tFinal = 6000.0
        tFinal = 50.0

        # Start a counter for the total simulation time
        simTime = 0.0

        self.fprint("dt: %.4f" % (self.problem.dt))
        self.fprint("tFinal: %.1f" % (tFinal))

        # ================================================================

        # Specify how frequently to save output files
        saveInterval = 10.0

        # Start a counter for the number of saved files
        saveCount = 0
        save_next_timestep = False

        # Generate file pointers for saved output
        # FIXME: This should use the .save method
        fp = []
        fp.append(File("%s/timeSeries/velocity.pvd" % (self.problem.dom.params.folder)))
        fp.append(File("%s/timeSeries/pressure.pvd" % (self.problem.dom.params.folder)))
        fp.append(File("%s/timeSeries/nu_T.pvd" % (self.problem.dom.params.folder)))

        if "turbine_force" in self.params.output:
            fp.append(File("%s/timeSeries/turbineForce.pvd" % (self.problem.dom.params.folder)))

        self.fprint("Saving Input Data",special="header")
        if "mesh" in self.params.output:
            self.problem.dom.Save(val=iter_val)
        if "initial_guess" in self.params.output:
            self.problem.bd.SaveInitialGuess(val=iter_val)
        if "height" in self.params.output and self.problem.dom.dim == 3:
            self.problem.bd.SaveHeight()
        # if "turbine_force" in self.params.output:
        #     self.problem.farm.SaveTurbineForce(val=iter_val)

        self.fprint("Finished",special="footer")

        # ================================================================

        self.fprint("")
        self.fprint("Calculating Boundary Conditions")

        # FIXME: This should use the boundary information in self.problem.bd.bcs
        bcu, bcp = self.GetBoundaryConditions(0.0)

        # ================================================================

        self.fprint("Assembling time-independent matrices")

        # Assemble left-hand side matrices
        A1 = assemble(self.problem.a1)
        A2 = assemble(self.problem.a2)
        A3 = assemble(self.problem.a3)

        # Apply boundary conditions to matrices
        [bc.apply(A1) for bc in bcu]
        [bc.apply(A2) for bc in bcp]

        # Assemble right-hand side vector
        b1 = assemble(self.problem.L1)
        b2 = assemble(self.problem.L2)
        b3 = assemble(self.problem.L3)

        # Apply bounday conditions to vectors
        [bc.apply(b1) for bc in bcu]
        [bc.apply(b2) for bc in bcp]

        # ================================================================

        self.fprint("Solving",special="header")
        self.fprint("Sim Time | Next dt | U_max")
        self.fprint("--------------------------")

        start = time.time()

        while simTime < tFinal:
            # Get boundary conditions specific to this timestep
            # bcu, bcp = self.GetBoundaryConditions(simTime/tFinal)
            # bcu = self.modifyInletVelocity(simTime, bcu)

            # Update the turbine force
            self.UpdateTurbineForce(simTime, 1) # Single turbine
            # self.UpdateTurbineForce(simTime, 2) # Dubs

            # Record the "old" max velocity (before this update)
            u_max_k1 = self.problem.u_k.vector().max()

            # Step 1: Tentative velocity step
            b1 = assemble(self.problem.L1, tensor=b1)
            [bc.apply(b1) for bc in bcu]
            solve(A1, self.problem.u_k.vector(), b1, 'gmres', 'default')

            # Step 2: Pressure correction step
            b2 = assemble(self.problem.L2, tensor=b2)
            [bc.apply(b2) for bc in bcp]
            solve(A2, self.problem.p_k.vector(), b2, 'gmres', 'hypre_amg')

            # Step 3: Velocity correction step
            b3 = assemble(self.problem.L3, tensor=b3)
            solve(A3, self.problem.u_k.vector(), b3, 'gmres', 'default')

            # Old <- New update step
            self.problem.u_k2.assign(self.problem.u_k1)
            self.problem.u_k1.assign(self.problem.u_k)
            self.problem.p_k1.assign(self.problem.p_k)

            # Record the updated max velocity
            u_max = self.problem.u_k.vector().max()

            # Update the simulation time
            simTime += self.problem.dt

            if save_next_timestep:
                # Read in new inlet values
                bcu = self.updateInletVelocityFromFile(saveCount, bcu)
                
                # Clean up simTime to avoid accumulating round-off error
                saveCount += 1
                simTime = saveInterval*saveCount

                # Save output files
                self.SaveTimeSeries(fp, simTime)

            # Adjust the timestep size, dt, for a balance of simulation speed and stability
            save_next_timestep = self.AdjustTimestepSize(saveInterval, simTime, u_max, u_max_k1)

            # After changing timestep size, A1 must be reassembled
            # FIXME: This may be unnecessary (or could be sped up by changing only the minimum amount necessary)
            A1 = assemble(self.problem.a1, tensor=A1)
            [bc.apply(A1) for bc in bcu]

            # Print some solver statistics
            self.fprint("%8.2f | %7.2f | %5.2f" % (simTime, self.problem.dt, u_max))

        stop = time.time()

        self.fprint("Finished",special="footer")
        self.fprint("Solve Complete: {:1.2f} s".format(stop-start),special="footer")

    # ================================================================

    def SaveTimeSeries(self, fp, simTime):

        # Save velocity files (pointer in fp[0])
        self.problem.u_k.rename('Velocity', 'Velocity')
        fp[0] << (self.problem.u_k, simTime)

        # Save pressure files (pointer in fp[1])
        self.problem.p_k.rename('Pressure', 'Pressure')
        fp[1] << (self.problem.p_k, simTime)

        # Save eddy viscosity files (pointer in fp[2])
        # nu_T_val = project(self.problem.nu_T, self.problem.fs.Q, solver_type='gmres')
        # nu_T_val.rename('nu_T', 'nu_T')
        # fp[2] << (nu_T_val, simTime)

        # Save turbine force files (pointer in fp[3])
        # if "turbine_force" in self.params.output:

        workaround = False

        if workaround:
            tf_value = project(self.problem.tf, self.problem.fs.V, solver_type='gmres')
            tf_value.rename('Turbine_Force', 'Turbine_Force')
            fp[3] << (tf_value, simTime)
        else:
            self.problem.tf.rename('Turbine_Force', 'Turbine_Force')
            fp[3] << (self.problem.tf, simTime)


    # ================================================================

    def AdjustTimestepSize(self, saveInterval, simTime, u_max, u_max_k1):

        # Set the CFL target (0.2 is a good value for stability and speed, YMMV)
        cfl_target = 0.2

        # Enforce a minimum timestep size
        dt_min = 0.01

        # Calculate the change in velocity using a first-order, backward difference
        dudt = u_max - u_max_k1

        # Calculate the projected velocity
        u_max_projected = u_max + dudt

        # Calculate the ideal timestep size (ignore file output considerations for now)
        dt_new = cfl_target * self.problem.dom.mesh.hmin() / u_max_projected

        # Move to larger dt slowly (smaller dt happens instantly)
        if dt_new > self.problem.dt:
            # Amount of new dt to use: 0 = none, 1 = all
            SOR = 0.5
            dt_new = SOR*dt_new + (1.0-SOR)*self.problem.dt

        # Calculate the time remaining until the next file output
        time_remaining = saveInterval - (simTime % saveInterval)

        # If the new timestep would jump past a save point, modify the new timestep size
        if dt_new + dt_min >= time_remaining:
            dt_new = time_remaining
            save_next_timestep = True
        else:
            save_next_timestep = False

        # Update both the Python variable and FEniCS constant
        self.problem.dt = dt_new
        self.problem.dt_c.assign(dt_new)

        # float(self.problem.dt_c) # to get the regular ol' variable

        return save_next_timestep

    # ================================================================

    def UpdateTurbineForce(self, simTime, turbsPerPlatform):
        coords = self.problem.fs.V.tabulate_dof_coordinates()
        coords = np.copy(coords[0::self.problem.dom.dim, :])

        # Pre allocate all numpy arrays and vectors
        tf_array = np.zeros(np.shape(coords))
        tf_vec = np.zeros(np.size(tf_array))
        xs = np.zeros(np.shape(coords))

        # Radius of the two "arms" measured from the hinge
        rad = 189.0

        if turbsPerPlatform == 1:
            rad = 0.0

        # Angle defined between the two "arms"
        phi = np.pi/3.0

        # Calculate the offset from the hinge to each turbine
        xp_offset = rad*np.cos(phi/2.0)
        yp_offset = rad*np.sin(phi/2.0)

        # delta_yaw = 0.0

        for k in range(self.problem.farm.numturbs):
            # Position of the kth turbune
            xpos = float(self.problem.farm.mx[k])
            ypos = float(self.problem.farm.my[k])
            
            if self.problem.dom.dim == 2:
                x0 = np.array([xpos, ypos])
            else:
                zpos = float(self.problem.farm.mz[k])
                x0 = np.array([xpos, ypos, zpos])

            # Yaw, thickness, radius, and mass of the kth turbine
            # If desired, shift each turbine by a constant amount
            # delta_yaw = np.pi/4.0*np.sin(np.pi*(simTime/1000.0 + k/self.problem.farm.numturbs))
            delta_yaw = 0.0

            yaw = float(self.problem.farm.myaw[k] + delta_yaw)
            W = float(self.problem.farm.W[k]/2.0)
            R = float(self.problem.farm.RD[k]/2.0)
            ma = float(self.problem.farm.ma[k])

            # Create a rotation matrix for this yaw angle
            A_rotation = self.RotationMatrix(yaw)

            # Rotate the turbine after shifting (x0, y0, z0) to the center of the turbine
            xs0 = np.dot(coords - x0, A_rotation)

            for doublet in range(turbsPerPlatform):

                offset = np.zeros(self.problem.dom.dim)
                offset[0] = xp_offset
                offset[1] = yp_offset*(-1)**doublet

                # Offset each turbine from the center of rotation
                xs = xs0 - offset

                # Normal to blades: Create the function that represents the Thickness of the turbine
                T_norm = 1.902701539733748
                T = np.exp(-(xs[:, 0]/W)**10.0)/(T_norm*W)

                # Tangential to blades: Create the function that represents the Disk of the turbine
                D_norm = 2.884512175878827
                if self.problem.dom.dim == 2:
                    D1 = (xs[:, 1]/R)**2.0
                else:
                    D1 = (xs[:, 1]/R)**2.0 + (xs[:, 2]/R)**2.0

                D = np.exp(-D1**5.0)/(D_norm*R**2.0)

                # Create the function that represents the force
                if self.problem.dom.dim == 2:
                    r = xs[:, 1]
                else:
                    r = np.sqrt(xs[:, 1]**2.0 + xs[:, 2]**2.0)

                F = 4.0*0.5*(np.pi*R**2.0)*ma/(1.0 - ma)*(r/R*np.sin(np.pi*r/R) + 0.5) * 1.0/.81831

                u_vec = self.problem.u_k1.vector()[:]
                ux = u_vec[0::self.problem.dom.dim]
                uy = u_vec[1::self.problem.dom.dim]
                uD = ux*np.cos(yaw) + uy*np.sin(yaw)

                tf_array[:, 0] = tf_array[:, 0] + F*T*D*np.cos(yaw)*uD**2.0
                tf_array[:, 1] = tf_array[:, 1] + F*T*D*np.sin(yaw)*uD**2.0


        # Riffle shuffle the array elements into a FEniCS-style vector
        for k in range(self.problem.dom.dim):
            tf_vec[k::self.problem.dom.dim] = tf_array[:, k]

        tf_vec[np.abs(tf_vec) < 1e-50] = 0.0

        # Set the vector elements
        self.problem.tf.vector()[:] = tf_vec

    # ================================================================


    def RotationMatrix(self, yaw):
        cosYaw = np.cos(yaw)
        sinYaw = np.sin(yaw)

        if self.problem.dom.dim == 2:
            A_rotation = np.array([[cosYaw, -sinYaw],
                                   [sinYaw,  cosYaw]])
        else:
            A_rotation = np.array([[cosYaw, -sinYaw, 0.0],
                                   [sinYaw,  cosYaw, 0.0],
                                   [   0.0,     0.0, 1.0]])

        return A_rotation

    # ================================================================


    def updateInletVelocityFromFile(self, saveCount, bcu):
        
        # Define tolerance
        tol = 1e-6

        # Define a function to identify the left wall
        def left_wall(x, on_boundary):
            return on_boundary and x[0] < self.problem.dom.x_range[0] + tol

        # Load each of the PyTurbSim outputs (saved as numpy arrays)
        uTotal = np.load('pyturbsim_outputs/turb_u.npy')
        vTotal = np.load('pyturbsim_outputs/turb_v.npy')
        wTotal = np.load('pyturbsim_outputs/turb_w.npy')
        y = np.load('pyturbsim_outputs/turb_y.npy')
        z = np.load('pyturbsim_outputs/turb_z.npy')


        DEBUGGING = False

        # Rescale y and z values to match existing domain
        # print(' og z = ', z)
        y = np.linspace(self.problem.dom.y_range[0], self.problem.dom.y_range[1], len(y))
        z = np.linspace(self.problem.dom.z_range[0], self.problem.dom.z_range[1], len(z))

        if DEBUGGING:
            y = np.array([self.problem.dom.y_range[0], self.problem.dom.y_range[1]])
            z = np.array([self.problem.dom.z_range[0], self.problem.dom.z_range[1]])

        # print('new z = ', z)
        # print('saveCount = ', saveCount)

        # Check to see if we have enough turbulence slices
        if saveCount > np.shape(uTotal)[2] - 1:
            raise ValueError("Ran out of turbulent inflow files! Run PyTurbSim with longer tFinal.")


        # Extract a single slice of u, v, and w data
        u = uTotal[:, :, saveCount]
        v = vTotal[:, :, saveCount]
        w = wTotal[:, :, saveCount]

        if DEBUGGING:
            u = np.array([[0.5, 0.0],
                          [0.0, 1.0]])
            v = np.array([[0.0, 0.0], [0.0, 0.0]])
            w = np.array([[0.0, 0.0], [0.0, 0.0]])

        # Get the coordinates using the vector funtion space, V
        coords = self.problem.fs.V.tabulate_dof_coordinates()
        coords = np.copy(coords[0::self.problem.dom.dim, :])

        # Create a function representing the inlet velocity
        vel_inlet_func = Function(self.problem.fs.V)

        # Create an array and vector to hold the u, v, w values at each grid point
        vel_inlet_array = np.zeros(np.shape(coords))
        vel_inlet_vector = np.zeros(np.size(vel_inlet_array))

        # For each coordinate, determine if it's on the boundary
        for k, xi in enumerate(coords):
            if xi[0] < self.problem.dom.x_range[0] + tol:

                # Get the interpolated value at this point
                ui = self.bilinearInterp(xi[1], xi[2], y, z, [u, v, w])

                # Assign this value to the corresponding spot in the velocity array
                vel_inlet_array[k, :] = ui

        # Riffle-shuffle the array elements into a FEniCS friendly vector
        for k in range(self.problem.dom.dim):
            vel_inlet_vector[k::self.problem.dom.dim] = vel_inlet_array[:, k]

        # Assign the function the vector of values
        vel_inlet_func.vector()[:] = vel_inlet_vector

        # Update the inlet velocity
        bcu[0] = DirichletBC(self.problem.fs.V, vel_inlet_func, left_wall)


        return bcu

    # ================================================================


    def bilinearInterp(self, xi, yi, x, y, velList):
        # Find the node index such that x[xptr-1] < xi < x[xptr]
        xptr = 1
        while x[xptr] < xi and xptr < len(x)-1:
            xptr += 1

        # Find the node index such that y[yptr-1] < yi < y[yptr]
        yptr = 1
        while y[yptr] < yi and yptr < len(y) - 1:
            yptr += 1

        # Initialize space for each interpolated component
        ui = np.zeros(len(velList))

        for index, u in enumerate(velList):
            # Get the value of the function at the four nodes surrounding the interpolation point
            u11 = u[yptr-1, xptr-1]
            u12 = u[yptr  , xptr-1]
            u21 = u[yptr-1, xptr  ]
            u22 = u[yptr  , xptr  ]

            # Calculate four weighted averages for each corner
            a11 = u11*(x[xptr] - xi       )*(y[yptr] - yi       )
            a12 = u12*(x[xptr] - xi       )*(yi      - y[yptr-1])
            a21 = u21*(xi      - x[xptr-1])*(y[yptr] - yi       )
            a22 = u22*(xi      - x[xptr-1])*(yi      - y[yptr-1])

            # Calculate the value of the function at the interpolation point
            ui[index] = 1.0/((x[xptr] - x[xptr-1])*(y[yptr] - y[yptr-1]))*(a11 + a12 + a21 + a22)

        return ui

    # ================================================================


    def modifyInletVelocity(self, simTime, bcu):

        # Define tolerance
        tol = 1e-6

        def left_wall(x, on_boundary):
            return on_boundary and x[0] < self.problem.dom.x_range[0] + tol

        vmax = self.problem.bd.vmax

        # Get the coordinates using the vector funtion space, V
        coords = self.problem.fs.V.tabulate_dof_coordinates()
        coords = np.copy(coords[0::self.problem.dom.dim, :])

        # Create a function representing to the inlet velocity
        vel_inlet_func = Function(self.problem.fs.V)

        inlet_type = 1

        if inlet_type == 1:
            # Create arrays for the steady, vortex, and combined velocities
            vel_steady = np.zeros(np.shape(coords))
            vel_steady[:, 0] = vmax
            # print(vmax)

            vel_vort = np.zeros(np.shape(coords))
            vel_inlet = np.zeros(np.shape(coords))

            # Specify the vortex radius
            vortRad = 1000
            vortRad2 = vortRad**2

            # Specify the vortex velocity and calculate its position from the starting point
            vortVel = 1.0

            period = 1000.0
            xd = period/2 - vortVel*(simTime%period)

            fac = 0.1
            sep = 650
            Tau = 1000

            for k, x in enumerate(coords):
                if x[0] < self.problem.dom.x_range[0] + tol:

                    # xd should replace x[0] in the following equations
                    if np.abs(xd) < 1e-3:
                        xd = 1e-3

                    cp = ((x[1] + sep/2)**2 + xd**2)/(4*Tau)
                    cn = ((x[1] - sep/2)**2 + xd**2)/(4*Tau)

                    # U-velocity
                    vel_inlet[k, 0] = fac*((1 - np.exp(-cp))/cp*(x[1] + sep/2) -\
                                           (1 - np.exp(-cn))/cn*(x[1] - sep/2)) + 1

                    # V-velocity
                    vel_inlet[k, 1] = fac*(-(1 - np.exp(-cp))/cp*xd +\
                                            (1 - np.exp(-cn))/cn*xd)

                    norm = np.sqrt(vel_inlet[k, 0]*vel_inlet[k, 0] + vel_inlet[k, 1]*vel_inlet[k, 1])

                    if norm > 10.0:
                        vel_inlet[k, 0] = vel_inlet[k, 0]/norm*10.0
                        vel_inlet[k, 1] = vel_inlet[k, 1]/norm*10.0

                    # dx = x - vortPos
                    # dist2 = dx[0]*dx[0] + dx[1]*dx[1]

                    # if dist2 < vortRad2:
                    #     theta = np.arctan2(dx[1], dx[0])
                    #     fac = 1.0 - np.sqrt(dist2/vortRad2)
                    #     vel_vort[k, 0] = -np.sin(theta)
                    #     vel_vort[k, 1] = np.cos(theta)
                    # else:
                    #     fac = 0.0
                    #     vel_vort[k, 0] = 0.0
                    #     vel_vort[k, 1] = 0.0

                    # vel_inlet[k, :] = (1.0-fac)*vel_steady[k, :] + vmax*fac*vel_vort[k, :]

        elif inlet_type == 2:
            jet_rad = 400

            vel_inlet = np.zeros(np.shape(coords))

            for k, x in enumerate(coords):
                if x[0] < self.problem.dom.x_range[0] + tol:
                    if np.abs(x[1]) < jet_rad:
                        thetaMax = 15.0/180.0*np.pi

                        theta = thetaMax*np.sin(simTime/1000*2*np.pi)

                        vel_inlet[k, 0] = 2.0*vmax*np.cos(theta)
                        vel_inlet[k, 1] = 2.0*vmax*np.sin(theta)
                    else:
                        vel_inlet[k, 0] = vmax
                        vel_inlet[k, 1] = 0.0


        # Riffle shuffle the array elements into a 1D vector
        vel_inlet_vector = np.zeros(np.size(vel_inlet))

        for k in range(self.problem.dom.dim):
            vel_inlet_vector[k::self.problem.dom.dim] = vel_inlet[:, k]

        # Assign the function the vector of values
        vel_inlet_func.vector()[:] = vel_inlet_vector


        # Update the inlet velocity
        bcu[0] = DirichletBC(self.problem.fs.V, vel_inlet_func, left_wall)

        return bcu

    # ================================================================

    def GetBoundaryConditions(self, simTime):
        # FIXME: This whole function should be deleted and its output
        # replaced with values already present in self.problem.bd.bcs

        # Define tolerance
        tol = 1e-6

        # Identify all the walls of the computational domain
        rad = (self.problem.dom.y_range[1] - self.problem.dom.y_range[0])/self.problem.dom.ny
        def single_fixed_pt(x, on_boundary):
            return on_boundary and x[0] < self.problem.dom.x_range[0]+tol and -1.1*rad < x[1] < 1.1*rad


        def left_wall(x, on_boundary):
            return on_boundary and x[0] < self.problem.dom.x_range[0] + tol
        def right_wall(x, on_boundary):
            return on_boundary and x[0] > self.problem.dom.x_range[1] - tol
        def bottom_wall(x, on_boundary):
            return on_boundary and x[1] < self.problem.dom.y_range[0] + tol
        def top_wall(x, on_boundary):
            return on_boundary and x[1] > self.problem.dom.y_range[1] - tol
        if self.problem.dom.dim == 3:
            def back_wall(x, on_boundary):
                return on_boundary and x[2] < self.problem.dom.z_range[0] + tol
            def front_wall(x, on_boundary):
                return on_boundary and x[2] > self.problem.dom.z_range[1] - tol

        # Build a list with the boundary conditions for velocity
        bcu = []

        # Get the max_vel value from the input parameters
        vmax = self.problem.bd.vmax

        use_variable_bc = False
        free_slip = True

        if use_variable_bc:
            # simTime in the range [0, 1] since it's divided by tFinal
            theta = np.pi/4.0 + np.pi/9.0*np.sin(simTime*2.0*np.pi)

            if theta < 0 or theta > 2.0*np.pi:
                theta = theta % (2.0*np.pi)

            # theta = np.pi/18.0
            ux = vmax*np.cos(theta)
            uy = vmax*np.sin(theta)


            # print(ux, uy)

            if theta < np.pi/2.0:
                # left and bottom
                bcu.append(DirichletBC(self.problem.fs.V, Constant((ux, uy)), left_wall))
                bcu.append(DirichletBC(self.problem.fs.V, Constant((ux, uy)), bottom_wall))
            elif theta < np.pi:
                # bottom and right
                bcu.append(DirichletBC(self.problem.fs.V, Constant((ux, uy)), bottom_wall))
                bcu.append(DirichletBC(self.problem.fs.V, Constant((ux, uy)), right_wall))
            elif theta < 3.0*np.pi/2.0:
                # right and top
                bcu.append(DirichletBC(self.problem.fs.V, Constant((ux, uy)), right_wall))
                bcu.append(DirichletBC(self.problem.fs.V, Constant((ux, uy)), top_wall))
            else:
                # top and left
                bcu.append(DirichletBC(self.problem.fs.V, Constant((ux, uy)), top_wall))
                bcu.append(DirichletBC(self.problem.fs.V, Constant((ux, uy)), left_wall))

        else:
            if self.problem.dom.dim == 2:
                bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0)), left_wall))
                #bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0)), right_wall))
                bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0)), bottom_wall))
                bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0)), top_wall))

            elif self.problem.dom.dim == 3:
                if free_slip:
                    inflow = Expression(('x[2] > 0 ? vmax*std::log(x[2]/0.01)/std::log(ph/0.01) : 0', '0', '0'), 
                        degree = 2, vmax = vmax, ph = self.problem.farm.HH[0])

                    # bcu.append(DirichletBC(self.problem.fs.V.sub(0), Constant(vmax), left_wall))
                    bcu.append(DirichletBC(self.problem.fs.V, inflow, left_wall))
                    # bcu.append(DirichletBC(self.problem.fs.V.sub(0), Constant(0), rightW))
                    bcu.append(DirichletBC(self.problem.fs.V.sub(1), Constant(0), bottom_wall))
                    bcu.append(DirichletBC(self.problem.fs.V.sub(1), Constant(0), top_wall))
                    bcu.append(DirichletBC(self.problem.fs.V.sub(2), Constant(0), back_wall))
                    bcu.append(DirichletBC(self.problem.fs.V.sub(2), Constant(0), front_wall))
                else:
                    bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0, 0)), left_wall))
                    # bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0, 0)), right_wall))
                    bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0, 0)), bottom_wall))
                    bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0, 0)), top_wall))
                    bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0, 0)), back_wall))
                    bcu.append(DirichletBC(self.problem.fs.V, Constant((vmax, 0, 0)), front_wall))

        # Build a list with the boundary conditions for pressure
        bcp = []


        if use_variable_bc:
            if theta < np.pi/2.0:
                # left and bottom
                bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), right_wall))
                bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), top_wall))
            elif theta < np.pi:
                # bottom and right
                bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), top_wall))
                bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), left_wall))
            elif theta < 3.0*np.pi/2.0:
                # right and top
                bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), left_wall))
                bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), bottom_wall))
            else:
                # top and left
                bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), bottom_wall))
                bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), right_wall))
        else:
            bcp.append(DirichletBC(self.problem.fs.Q, Constant(0), right_wall))

        return bcu, bcp

# ================================================================

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
        if self.params["domain"]["type"] not in ["cylinder","interpolated"]:
            raise ValueError("A cylinder, or interpolated cylinder domain is required for a Multi-Angle Solver")
        self.orignal_solve = super(MultiAngleSolver, self).Solve
        self.init_wind = self.params["solver"].get("init_wind_angle", 0.0)
        self.final_wind = self.params["solver"].get("final_wind_angle", 2.0*pi)
        self.num_wind = self.params["solver"]["num_wind_angles"]
        self.angles = np.linspace(self.init_wind,self.final_wind,self.num_wind)

    def Solve(self):
        for i, theta in enumerate(self.angles):
            self.fprint("Performing Solve {:d} of {:d}".format(i+1,len(self.angles)),special="header")
            self.fprint("Wind Angle: "+repr(theta))
            if i > 0 or not near(theta,self.init_wind):
                self.ChangeWindAngle(theta)
            self.orignal_solve(iter_val=theta)
            self.fprint("Finished Solve {:d} of {:d}".format(i+1,len(self.angles)),special="footer")